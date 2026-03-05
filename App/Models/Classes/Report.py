import csv
import io
import pytz
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.enums import TA_CENTER
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from App.Models.Classes.TimesheetManager import ViewTimeSheetManager
from App.Models.Classes.GetUser import GetUser
from App.Models.Classes.UserManager import UserAuthManager
from App.Models.Classes.customerVerifier import CustomerUserVerifier
from Models.db.schemas import AdminTimesheet
from decimal import Decimal
from collections import defaultdict
from Models.utils.error_handler import ErrorHandler
import json
error = ErrorHandler()

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, json_data):
        self.data = json_data
        self.fieldnames = self._get_fieldnames()

    def _get_fieldnames(self):
        if not self.data:
            return []
        return list(self.data[0].keys()) + ['TotalHoursWorked']

    def _group_data(self):
        grouped_data = defaultdict(list)
        total_hours_by_user = defaultdict(Decimal)

        for entry in self.data:
            first_name = entry.get('FullName')
            hours_worked = Decimal(entry.get('HoursWorked', 0))
            grouped_data[first_name].append(entry)
            total_hours_by_user[first_name] += hours_worked

        for first_name, entries in grouped_data.items():
            for entry in entries:
                entry['TotalHoursWorked'] = float(total_hours_by_user[first_name])

        return grouped_data

    def generate_csv(self):
        grouped_data = self._group_data()
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=self.fieldnames)
        writer.writeheader()

        for first_name, entries in grouped_data.items():
            writer.writerows(entries)
            writer.writerow({})  # Add an empty row after each user's data
        
        return csv_buffer.getvalue()

    def generate_pdf(self):
        grouped_data = self._group_data()
        pdf_buffer = io.BytesIO()
        styles = getSampleStyleSheet()
        styleN = styles['BodyText']
        header_style = ParagraphStyle(
            name='Header', fontSize=10, textColor=colors.whitesmoke, alignment=TA_CENTER)

        header = [Paragraph(f'<b>{col}</b>', header_style) for col in self.fieldnames]
        table_data = [header]

        for first_name, entries in grouped_data.items():
            for entry in entries:
                row = [Paragraph(str(entry.get(field, '')), styleN) for field in self.fieldnames]
                table_data.append(row)

        landscape_size = landscape(letter)
        pdf = SimpleDocTemplate(pdf_buffer, pagesize=landscape_size)
        elements = []

        num_columns = len(self.fieldnames)
        col_widths = [landscape_size[0] / num_columns] * num_columns

        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        pdf.build(elements)
        return pdf_buffer.getvalue()

    def get_files(self):
        csv_content = self.generate_csv()
        pdf_content = self.generate_pdf()
        return {
            'csv': ('report.csv', csv_content, 'text/csv'),
            'pdf': ('report.pdf', pdf_content, 'application/pdf')
        }

class TimesheetReportManager:
    def __init__(self, db: Session, request: Request):
        self.db = db
        self.shortname = None
        self.request= request

    def verify_admin(self, token_info):
        if token_info["role"] not in ["Admin", "Manager"]:
            return error.error("You do not have the permission to perform this action", 401, "Unauthorized")

    def verify_customer_and_user(self, company_portal_url, user_id):
        verifier = CustomerUserVerifier(self.db)
        result = verifier.verify_customer_and_user(company_portal_url, user_id)
        if isinstance(result, JSONResponse):
            return error.error(result.content["message"], result.status_code, "Unauthorized")
        return result

    def setup_tables(self, customer):
        self.users_table = f"{customer.SchemaName}.tb_{
            customer.ShortName}_user_info"
        self.timesheet_table = f"{customer.SchemaName}.tb_{
            customer.ShortName}_timesheet"
        self.request_table = f"{customer.SchemaName}.tb_{
            customer.ShortName}_requests"

    def get_timeoff_requests(self, month: int, year: int, user_uuids: List[str]):
        try:
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)

            query = text(
                f"""
                SELECT "UserUUID", "RequestDetails"
                FROM {self.request_table}
                WHERE "UserUUID" IN :user_uuids
                AND "RequestStatus" = 'Approved' AND "RequestType" = 'TimeOff'
                """
            )
            timeoff_requests = self.db.execute(query, {
                "user_uuids": tuple(user_uuids)
            }).fetchall()
            filtered_requests = []
            for row in timeoff_requests:
                request_details = row[1]
                start_date_str = request_details.get('StartDate')
                if start_date_str:
                    request_start_date = datetime.fromisoformat(
                        start_date_str.rstrip('Z'))
                    if start_date <= request_start_date.replace(tzinfo=None) < end_date:
                        filtered_requests.append({
                            "UserUUID": str(row[0]),
                            "RequestDetails": request_details
                        })

            return filtered_requests
        except Exception as e:
            logger.error(f"Error in get_timeoff_requests: {str(e)}")
            raise e

    def get_user_info(self, user_ids: Optional[List[int]] = None):
        try:
            if user_ids:
                user_query = text(
                    f"""
                    SELECT "UserUUID", "FirstName", "LastName" FROM {self.users_table}
                    WHERE "ID" IN :user_ids
                    """
                )
                user_results = self.db.execute(
                    user_query, {"user_ids": tuple(user_ids)}).fetchall()
            else:
                user_query = text(
                    f"""
                    SELECT "UserUUID", "FirstName", "LastName" FROM {self.users_table}
                    """
                )
                user_results = self.db.execute(user_query).fetchall()

            if not user_results:
                logger.warning("No users found with 'user' role")
                return error.error("No users found with 'user' role", 404, "User Not Found")

            return {str(row[0]): f"{row[1]} {row[2]}" for row in user_results if len(row) >= 3}
        except Exception as e:
            logger.error(f"Error in get_user_info: {str(e)}")
            raise e

    def get_hours_worked(self, month: int, year: int, user_uuids: List[str], status: Optional[str] = None):
        try:
            utc = pytz.UTC
            start_date = utc.localize(datetime(year, month, 1))
            if month == 12:
                end_date = utc.localize(datetime(year + 1, 1, 1))
            else:
                end_date = utc.localize(datetime(year, month + 1, 1))

            # current_date = datetime.now()
            # end_date = min(end_date, current_date)
            print( start_date, end_date)
            query = text(
                f"""
                SELECT "UserUUID", "Date", "HoursWorked", "ClientName", "Status", "ProjectBucket"
                FROM {self.timesheet_table}
                WHERE "Date" >= :start_date AND "Date" < :end_date
                AND "UserUUID" IN :user_uuids
                {" AND \"Status\" = :status" if status else ""}
                ORDER BY "Date"
                """
            )
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "user_uuids": tuple(user_uuids)
            }
            if status:
                params["status"] = status

            timesheets = self.db.execute(query, params).fetchall()

            return [
                {
                    "UserUUID": str(row[0]),
                    "Date": row[1],
                    "HoursWorked": float(row[2]),
                    "ClientName": row[3] or "Unspecified",
                    "Status": row[4],
                    "ProjectBucket": row[5] or "Unspecified"
                }
                for row in timesheets
            ]
        except Exception as e:
            logger.error(f"Error in get_hours_worked: {str(e)}")
            raise e
    
    def _get_week_start_end(self, current_date):
        """
        Calculate the start and end dates of a week, properly handling month boundaries
        """
        # Get the first and last day of the month
        first_day_of_month = current_date.replace(day=1)
        next_month = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
        last_day_of_month = next_month - timedelta(days=1)
        
        # Calculate the complete week boundaries
        current_weekday = current_date.weekday()
        week_start = current_date - timedelta(days=current_weekday)
        week_end = week_start + timedelta(days=6)
        
        # If the week spans multiple months, only include days within the current month
        if week_start.month != current_date.month:
            week_start = first_day_of_month
        if week_end.month != current_date.month:
            week_end = last_day_of_month
            
        return week_start, week_end

    def convert_to_client_timezone(self, utc_date, client_timezone):
        if isinstance(utc_date, str):
            utc_date = datetime.strptime(utc_date, '%Y-%m-%d')  # Adjust format as needed
        
        try:
            # Get timezone object from string
            client_tz = pytz.timezone(client_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            # Fall back to UTC if timezone is invalid
            client_tz = pytz.UTC
        
        # Make the date timezone-aware if it isn't already
        if utc_date.tzinfo is None:
            utc_date = pytz.utc.localize(utc_date)
        
        # Convert to client timezone
        return utc_date.astimezone(client_tz)

    def group_timesheets_and_timeoff_by_week(self, timesheets):
            # Initialize defaultdict structures for regular timesheets and timeoff
            grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(
                lambda: {"ApprovedHours": 0, "DeniedHours": 0, "PendingHours": 0}
            )))
            timeoff_grouped = defaultdict(lambda: defaultdict(lambda: {
                "ApprovedHours": 0,
                "DeniedHours": 0,
                "PendingHours": 0
            }))
            # Sort timesheets by date to ensure consistent processing
            sorted_timesheets = sorted(timesheets, key=lambda x: x['Date'])
            client_timezone = self.request.headers.get('X-Timezone', 'UTC')
            for timesheet in sorted_timesheets:
                print("timdata", timesheet)
                utc_date = timesheet['Date']
                client_date = self.convert_to_client_timezone(utc_date, client_timezone)
                week_start, week_end = self._get_week_start_end(client_date)
                week_key = f"{week_start.strftime('%b %d, %Y')} - {week_end.strftime('%b %d, %Y')}"
                user_uuid = str(timesheet['UserUUID'])
                status = timesheet['Status']
                hours = float(timesheet['HoursWorked'])
                # Check if this is a timeoff entry
                is_timeoff = timesheet.get('ProjectBucket', '').lower().startswith('time off')

                if is_timeoff:
                    # Handle timeoff entries
                    if status == 'Approved':
                        timeoff_grouped[user_uuid][week_key]["ApprovedHours"] += hours
                    elif status == 'Denied':
                        timeoff_grouped[user_uuid][week_key]["DeniedHours"] += hours
                    elif status == 'Pending':
                        timeoff_grouped[user_uuid][week_key]["PendingHours"] += hours
                else:
                    # Handle regular timesheet entries
                    client_name = timesheet['ClientName']
                    if status == 'Approved':
                        grouped[user_uuid][client_name][week_key]["ApprovedHours"] += hours
                    elif status == 'Denied':
                        grouped[user_uuid][client_name][week_key]["DeniedHours"] += hours
                    elif status == 'Pending':
                        grouped[user_uuid][client_name][week_key]["PendingHours"] += hours

            # Convert defaultdict to regular dict before returning
            return dict(grouped), dict(timeoff_grouped)
    

    def matches_filter(ts):
        if not filterBy:
            return True

        if "Status" in filterBy and ts.get("Status", "").lower() != filterBy["Status"].lower():
            return False

        if "Name" in filterBy:
            full_name = (ts.get("FullName") or "").lower()
            if filterBy["Name"].lower() not in full_name:
                return False

        if "Client" in filterBy:
            if filterBy["Client"].lower() not in (ts.get("ClientName") or "").lower():
                return False

        if "Month" in filterBy:
            if str(ts.get("Month")) != str(filterBy["Month"]):
                return False

        if "Period" in filterBy:
            try:
                start_str, end_str = [d.strip() for d in filterBy["Period"].split("to")]
                from datetime import datetime
                start = datetime.fromisoformat(start_str)
                end = datetime.fromisoformat(end_str)
                ts_date = datetime.fromisoformat(ts.get("Date"))
                if not (start <= ts_date <= end):
                    return False
            except Exception as err:
                logger.warning(f"Ignoring invalid period filter: {err}")
                return False

        return True

    def generate_report(self, month: int, year: int, status: Optional[str], user_ids: Optional[List[int]] = None, own: Optional[int]= None, filterBy: Optional[str] = None):
        try:           
            tim = ViewTimeSheetManager(self.db, self.portal, self.token)
            user_info = self.get_user_info(user_ids)
            user_uuids = list(user_info.keys())
            # timesheets = self.get_hours_worked(month, year, user_uuids, status)
            day = str(f"{year}-{month}")
            timesheets = tim.get_time_sheets(day=day, own=own, status=status, filterBy=filterBy)
            timeoff_requests = self.get_timeoff_requests(month, year, user_uuids)
            grouped_data, timeoff_data = self.group_timesheets_and_timeoff_by_week(timesheets)
            def calculate_total_hours(timesheets, status_filter, exclude_timeoff=True):
                return sum(
                    float(timesheet['HoursWorked'])
                    for timesheet in timesheets
                    if timesheet['Status'] == status_filter and 
                    (not exclude_timeoff or not timesheet.get('ProjectBucket', '').lower().startswith('timeoff'))
                )

            total_approved_hours = calculate_total_hours(timesheets, 'Approved')
            total_denied_hours = calculate_total_hours(timesheets, 'Denied')
            total_pending_hours = calculate_total_hours(timesheets, 'Pending')

            # Aggregate total timeoff hours
            total_timeoff_hours = sum(
                sum(week_data['ApprovedHours'] + week_data['DeniedHours'] + week_data['PendingHours']
                    for week_data in user_weeks.values())
                for user_weeks in timeoff_data.values()
            )

            # Initialize the result structure
            result = {
                "total_approved_hours": total_approved_hours,
                "total_denied_hours": total_denied_hours,
                "total_pending_hours": total_pending_hours,
                "total_timeoff_hours": total_timeoff_hours,
                "users": {}
            }

            # Process timesheets
            def process_user_data(user_uuid, client_data, timeoff_data):
                user_result = {}
                for client_name, weeks_data in client_data.items():
                    if client_name == self.shortname:  # Skip shortname
                        continue
                    client_result = {
                        week_key: {
                            "ApprovedHours": data.get("ApprovedHours", 0),
                            "DeniedHours": data.get("DeniedHours", 0),
                            "PendingHours": data.get("PendingHours", 0)
                        }
                        for week_key, data in weeks_data.items()
                    }
                    if client_result:  # Only add if there is data
                        user_result[client_name] = client_result

                # Add Time Off data
                if user_uuid in timeoff_data:
                    timeoff_result = {
                        week_key: {
                            "ApprovedHours": status_hours.get("ApprovedHours", 0),
                            "DeniedHours": status_hours.get("DeniedHours", 0),
                            "PendingHours": status_hours.get("PendingHours", 0)
                        }
                        for week_key, status_hours in timeoff_data[user_uuid].items()
                    }
                    if timeoff_result:  # Only add if there is data
                        user_result["Time Off"] = timeoff_result

                return user_result

            for user_uuid, client_data in grouped_data.items():
                user_name = user_info.get(user_uuid, f"Unknown User ({user_uuid})")
                user_result = process_user_data(user_uuid, client_data, timeoff_data)
                if user_result:  # Only add users with data
                    result["users"][user_name] = user_result

            return result

        except Exception as e:
            logger.error(f"Error in generate_report: {str(e)}")
            raise e


    async def admin_timesheet(self, data: AdminTimesheet, token_info: dict):
        GetUser(self.db, data.Company_Portal_Url).verify_user(token_info)
        self.portal = data.Company_Portal_Url
        self.token = token_info
        try:
            customer, user = self.verify_customer_and_user(data.Company_Portal_Url, token_info["Id"])
            self.setup_tables(customer)
            self.shortname = customer.ShortName
                
            user_id = token_info["Id"]
            if token_info['role'] in ['user', 'HR'] or (token_info['role'] == "Manager" and data.own == 1):
                id = UserAuthManager(self.db, data.Company_Portal_Url)._get_user_by_uuid(user_id)["ID"]
                report = self.generate_report(data.month, data.year, data.status, [id], own=data.own, filterBy=data.filterBy)
            else:
                report = self.generate_report(data.month, data.year, data.status, data.users, own=data.own, filterBy=data.filterBy)
            return report
        except Exception as e:
            logger.error(f"An unexpected error occurred in admin_timesheet: {str(e)}")
            raise e
