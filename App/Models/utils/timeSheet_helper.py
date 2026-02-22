import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta


def get_first_monday_of_month(year, month):
    first_day_of_month = datetime(year, month, 1)
    first_monday = first_day_of_month + \
        timedelta(days=(7 - first_day_of_month.weekday()) % 7)
    return first_monday


def get_week_ranges(year, month):
    first_monday = get_first_monday_of_month(year, month)
    week_ranges = []
    current_start = first_monday
    while current_start.month == month:
        current_end = current_start + timedelta(days=6)
        week_ranges.append((current_start.date(), current_end.date()))
        current_start = current_start + timedelta(days=7)
    return week_ranges


def get_month_range(year, month):
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1).date()
    end_date = datetime(year, month, last_day).date()
    return start_date, end_date


def group_timesheets_for_period(timesheets, start_date, end_date):
    def group_key(entry): return (
        entry['ClientName'], entry['ProjectName'], entry['ProjectBucket'])
    project_groups = defaultdict(lambda: {
        'ID': [],
        'client_name': '',
        'project_name': '',
        'task': '',
        'total_hours': 0,
        'attachment': set(),
        'status': None
    })

    for entry in timesheets:
        entry_date = ensure_date(entry['Date'])
        if start_date <= entry_date <= end_date:
            key = group_key(entry)
            group = project_groups[key]
            group['client_name'] = entry['ClientName']
            group['project_name'] = entry['ProjectName']
            group['task'] = entry['ProjectBucket']
            group['total_hours'] += entry['HoursWorked']
            group['attachment'].add(entry['TimesheetAttachmentURL'])
            group['ID'].append(entry['ID'])

            if entry['Status'] == 'Pending' or group['status'] is None:
                group['status'] = entry['Status']

    # Convert sets to lists for JSON serialization
    for group in project_groups.values():
        group['attachment'] = list(group['attachment'])

    return list(project_groups.values())


def ensure_date(date_value):
    if isinstance(date_value, str):
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    elif isinstance(date_value, datetime):
        return date_value.date()
    elif isinstance(date_value, date):
        return date_value
    else:
        raise ValueError(f"Unsupported date type: {type(date_value)}")


def group_timesheets(weekly_timesheets, group_by):
    grouped_timesheets = {}

    if group_by == 'month':
        # Assume all timesheets are for the same month
        if weekly_timesheets:
            entry_date = ensure_date(weekly_timesheets[0]['Date'])
            start_date, end_date = get_month_range(
                entry_date.year, entry_date.month)
            month_key = start_date.strftime("%Y-%m")
            grouped_timesheets[month_key] = group_timesheets_for_period(
                weekly_timesheets, start_date, end_date)
    else:
        for week, timesheets in weekly_timesheets.items():
            def group_key(entry): return (
                entry['ClientName'], entry['ProjectName'], entry['ProjectBucket'])
            project_groups = defaultdict(lambda: {
                'ID': [],
                'client_name': '',
                'project_name': '',
                'task': '',
                'total_hours': 0,
                'attachment': set(),
                'status': set()
            })

            for entry in timesheets:
                key = group_key(entry)
                group = project_groups[key]
                group['client_name'] = entry['ClientName']
                group['project_name'] = entry['ProjectName']
                group['task'] = entry['ProjectBucket']
                group['total_hours'] += entry['HoursWorked']
                group['attachment'].add(entry['TimesheetAttachmentURL'])
                group['ID'].append(entry['ID'])
                if entry['Status'] == 'Pending' or group['status'] is None:
                    group['status'] = entry['Status']
                else:
                    group['status'] = entry['Status']

            # Convert sets to lists for JSON serialization
            for group in project_groups.values():
                group['attachment'] = list(group['attachment'])

            grouped_timesheets[week] = list(project_groups.values())

    return grouped_timesheets


def clean_data(data):
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data(i) for i in data]
    elif isinstance(data, float) and (data != data):  # Check if data is NaN
        return None
    return data
