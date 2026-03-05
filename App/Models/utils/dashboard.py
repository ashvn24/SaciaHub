from collections import defaultdict
from datetime import date, datetime
import pytz
from sqlalchemy.sql import text

from App.Models.Classes.ClientManager import ClientManager
from App.Models.Classes.ProjectManager import ProjectManager
from App.Models.Classes.SOWManager import SOWManager
from Models.utils.timeSheet_helper import get_month_range, get_week_ranges, group_timesheets


def convert_to_user_timezone(dt, tz):
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(tz)
    elif isinstance(dt, date):
        return dt  # Return date object as is
    return dt


def fetch_timesheets(db, time_sheet_table, token_info, Day=None, Week=None, Month=None, portalurl= None):
    query_params = {}
    filter_condition = ""
    print("timesheet")
    if Day:
        # Filter by specific day\
        year, month = map(int, Day.split('-'))
        startDate, endDate = get_month_range(year, month)
        filter_condition = 'WHERE "UserUUID" = :UserUUID AND "Date" >= :start_date AND "Date" < :end_date'
        query_params["UserUUID"] = token_info['Id']
        query_params["Month"] = Day
        query_params["start_date"] = startDate
        query_params["end_date"] = endDate

    elif Week:
        # Filter by week
        year, month = map(int, Week.split('-'))
        week_ranges = get_week_ranges(year, month)
        filter_condition = 'WHERE "UserUUID" = :UserUUID AND "Date" BETWEEN :StartDate AND :EndDate'
        query_params["StartDate"] = min(start for start, end in week_ranges)
        query_params["EndDate"] = max(end for start, end in week_ranges)
        query_params["UserUUID"] = token_info['Id']

    elif Month:
        # Filter by month
        year, month = map(int, Month.split('-'))
        start_date, end_date = get_month_range(year, month)
        filter_condition = 'WHERE "UserUUID" = :UserUUID AND "Date" BETWEEN :StartDate AND :EndDate'
        query_params["UserUUID"] = token_info['Id']
        query_params["StartDate"] = start_date
        query_params["EndDate"] = end_date

    # Query to fetch timesheets for the given period, ordered by Date
    query = text(
        f"""
        SELECT "ID", "UserUUID", "ClientUUID", "ClientName", "ProjectName", "ProjectUUID", "SOWName", "SOWUUID", "User_Manager", "ProjectBucket",
               "Month", "Date", "StartDate", "EndDate", "WorkDescription", "HoursWorked", "Status", "TimesheetAttachmentURL", "ApprovedBy", "DeniedBy"
        FROM {time_sheet_table}
        {filter_condition}
        ORDER BY "Date" DESC LIMIT 3
        """
    )
    
    user_table = f"{time_sheet_table.split('.')[0]}.tb_{time_sheet_table.split('.')[1].split('_')[1]}_user_info"
    print("User Table: ", user_table)
    processed_query = text(f"""
        SELECT "FirstName", "LastName"
        FROM {user_table}
        WHERE "UserUUID" = :UserUUID
    """)

    result = db.execute(query, query_params)
    rows = result.mappings().all()
    processed_by_name = None
    
    for row in rows:
        # ✅ Get the approver or denier UUID
        processed_user_uuid = row.get("ApprovedBy") or row.get("DeniedBy")
        if processed_user_uuid:
            processed_result = db.execute(
                processed_query, {"UserUUID": processed_user_uuid}).mappings().fetchone()
            if processed_result:
                processed_by_name = f"{processed_result['FirstName']} {processed_result['LastName']}"

    # tz = pytz.timezone(user_timezone)
    sowdata = SOWManager(db, token_info, portalurl)
    cdata = ClientManager(db, token_info, portalurl)
    pdata = ProjectManager(db, token_info, portalurl)

    # Convert query result to list of dictionaries
    timesheets = [
        {
            "ID": row["ID"],
            "UserUUID": row["UserUUID"],
            "ClientName": cdata._get_client(clientuuid= row["ClientUUID"])[0]["ClientName"] if row["ClientUUID"] else row["ClientName"],
            "ProjectName": pdata._get_project(projectuuid= row["ProjectUUID"])[0]["ProjectName"] if row["ProjectUUID"] else row["ProjectName"],
            "SOWName": sowdata._get_sow(sowuuid = row["SOWUUID"])[0]["SOWName"] if row["SOWUUID"] else row["SOWName"],
            "User_Manager": row["User_Manager"],
            "ProjectBucket": row["ProjectBucket"],
            "Month": row["Month"],
            # "Date": convert_to_user_timezone(row["Date"], tz),
            # "StartDate": convert_to_user_timezone(row["StartDate"], tz),
            # "EndDate": convert_to_user_timezone(row["EndDate"], tz),
            "Date": row["Date"],
            "StartDate": row["StartDate"],
            "EndDate": row["EndDate"],
            "Notes": row["WorkDescription"],
            "HoursWorked": row["HoursWorked"],
            "Status": row["Status"],
            "TimesheetAttachmentURL": row["TimesheetAttachmentURL"],
            "ProcessedBy": processed_by_name,
        } for row in rows
    ]

    if Day:
        return timesheets

    if Week:
        # Organize data week-wise
        year, month = map(int, Week.split('-'))
        week_ranges = get_week_ranges(year, month)
        weekly_timesheets = defaultdict(list)

        for start_date, end_date in week_ranges:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            for ts in timesheets:
                # Assuming ts_date is a datetime.datetime object
                ts_date = ts["Date"]
                if isinstance(ts_date, datetime):
                    ts_datetime = ts_date
                else:
                    ts_datetime = datetime.combine(
                        ts_date, datetime.min.time())

                print(f"ts_datetime type: {type(ts_datetime)}")

                if ts_datetime.tzinfo is not None:
                    ts_datetime = ts_datetime.replace(tzinfo=None)

                if start_datetime <= ts_datetime <= end_datetime:
                    weekly_timesheets[f"{start_date} to {end_date}"].append(ts)

        return group_timesheets(weekly_timesheets, group_by='week')

    if Month:
        return group_timesheets(timesheets, group_by='month')


def request_dashboard(db, request_table, token_info, Type):
    query = text(
        f"""
            SELECT "ID", "RequestUUID", "RequestType", "RequestDetails", "RequestDescription",
                   "RequestPriority", "RequestStatus", "RequestAttachmentURL", "CreationTimeAndDate","ApprovedBy", "DeniedBy"
            FROM {request_table}
            WHERE "UserUUID" = :UserUUID AND "RequestType" = :RequestType
            ORDER BY "CreationTimeAndDate" DESC LIMIT 3
            """
    )
    result = db.execute(
        query, {"UserUUID": token_info['Id'], "RequestType": Type})
    rows = result.mappings().all()
    
    user_table = f"{request_table.split('.')[0]}.tb_{request_table.split('.')[1].split('_')[1]}_user_info"
    print("User Table: ", user_table)
    processed_query = text(f"""
        SELECT "FirstName", "LastName"
        FROM {user_table}
        WHERE "UserUUID" = :UserUUID
    """)

    processed_by_name = None
    for row in rows:
        # ✅ Get the approver or denier UUID
        processed_user_uuid = row.get("ApprovedBy") or row.get("DeniedBy")
        if processed_user_uuid:
            processed_result = db.execute(
                processed_query, {"UserUUID": processed_user_uuid}).mappings().fetchone()
            if processed_result:
                processed_by_name = f"{processed_result['FirstName']} {processed_result['LastName']}"
    

    requests = [
        
        {"ID": row["ID"],
         "RequestUUID": row["RequestUUID"],
         "RequestType": row["RequestType"],
         "RequestDetails": row["RequestDetails"],
         "RequestDescription": row["RequestDescription"],
         "RequestPriority": row["RequestPriority"],
         "RequestStatus": row["RequestStatus"],
         "RequestAttachmentURL": row["RequestAttachmentURL"],
         "CreatedOn": row["CreationTimeAndDate"],
         "ProcessedBy": processed_by_name,
         } for row in rows
    ]

    return requests
