import calendar
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy.sql import text
from Models.utils.timeSheet_helper import get_week_ranges
from Models.db.db_connection import SessionLocal, engine

session = SessionLocal(bind=engine)


class TimesheetManager:
    def __init__(self, timesheetTable):
        self.db = session
        self.time_sheet_table = timesheetTable

    def get_timesheets(self, month, year, users=None):
        query_params = {}

        start_date, end_date = self._get_date_range(year, month)
        print("date", start_date, end_date)
        filter_condition = self._build_filter_condition(
            start_date, end_date, users, query_params
        )

        query = self._build_query(filter_condition)
        result = self.db.execute(query, query_params)
        rows = result.mappings().all()
        # # Convert query result to list of dictionaries
        timesheets = [
            {
                "ID": row["ID"],
                "UserUUID": row["UserUUID"],
                "ClientName": row["ClientName"],
                "ProjectName": row["ProjectName"],
                "SOWName": row["SOWName"],
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
            }
            for row in rows
        ]
        return self.weeklytimesheets(year, month, timesheets)

    def _get_date_range(self, year, month):
        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day}"
        return start_date, end_date

    def _build_filter_condition(self, start_date, end_date, users, query_params):
        filter_condition = 'WHERE "Date" BETWEEN :StartDate AND :EndDate'
        query_params["StartDate"] = start_date
        query_params["EndDate"] = end_date

        if users:
            filter_condition += ' AND "UserUUID" IN :UserUUID'
            query_params["UserUUID"] = tuple(users)

        return filter_condition

    def _build_query(self, filter_condition):
        return text(
            f"""
            SELECT "ID", "UserUUID", "ClientName", "ProjectName", "SOWName", "User_Manager", "ProjectBucket",
                   "Month", "Date", "StartDate", "EndDate", "WorkDescription", "HoursWorked", "Status", "TimesheetAttachmentURL"
            FROM {self.time_sheet_table}
            {filter_condition}
            ORDER BY "ID", "Date" DESC
            """
        )

    def weeklytimesheets(self, year, month, timesheets):
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

                # print(f"ts_datetime type: {type(ts_datetime)}")

                if ts_datetime.tzinfo is not None:
                    ts_datetime = ts_datetime.replace(tzinfo=None)

                if start_datetime <= ts_datetime <= end_datetime:
                    weekly_timesheets[f"{start_date} to {end_date}"].append(ts)

        return weekly_timesheets

    def get_all_weeks(self, year, month):
        today = datetime.now()
        start_date = datetime(year, month, 1)
        end_date = min(
            datetime(year, month, calendar.monthrange(year, month)[1]), today
        )

        weeks = []
        current = start_date - timedelta(days=start_date.weekday())
        while current <= end_date:
            week_end = min(current + timedelta(days=6), end_date)
            weeks.append((current.date(), week_end.date()))
            current += timedelta(days=7)

        return weeks

    def get_user_timesheet(self, user_id, month, year):
        return self.get_timesheets(month, year, users=[user_id])

    def get_all_timesheets(self, month, year):
        return self.get_timesheets(month, year)
