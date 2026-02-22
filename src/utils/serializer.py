"""
Data serialization utilities.
Migrated from App/Models/utils/serializer.py.
"""

import json
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError


def make_serializable(data):
    """Recursively convert non-serializable types to strings."""
    if isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_serializable(item) for item in data]
    elif isinstance(data, (datetime, date, UUID)):
        return str(data)
    return data


def process_user_data(data):
    """Process user data by removing internal fields and parsing JSON strings."""
    excluded_keys = {"TABLEUUID", "ID", "UserUUID", "Created_date"}
    processed_data = {k: v for k, v in data.items() if k not in excluded_keys}

    for key, value in processed_data.items():
        if isinstance(value, str):
            try:
                processed_data[key] = json.loads(value)
            except json.JSONDecodeError:
                pass

    return format_uan_data_as_table(processed_data)


def serialize_non_null_data(user):
    """Serialize non-null data from a dict or ORM object."""
    if isinstance(user, dict):
        return process_user_data({k: v for k, v in user.items() if v is not None})

    try:
        return process_user_data(
            {
                attr.key: getattr(user, attr.key)
                for attr in class_mapper(type(user)).attrs
                if getattr(user, attr.key) is not None
            }
        )
    except UnmappedClassError:
        raise ValueError("Provided object is not an ORM-mapped instance")


def format_uan_data_as_table(json_data):
    """Format UAN verification data as HTML table."""
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            return "<html><body><p>Error: Invalid JSON data provided</p></body></html>"
    else:
        data = json_data

    uan_verification = data.get("UAN_Verification", {})
    employment_records = uan_verification.get("msg", [])

    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "    <title>UAN Verification Details</title>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }",
        "        .container { max-width: 900px; margin: 0 auto; background: #fff; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }",
        "        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }",
        "        h2 { color: #2c3e50; margin-top: 30px; }",
        "        table { width: 100%; border-collapse: collapse; margin: 20px 0; }",
        "        th, td { padding: 12px 15px; border: 1px solid #ddd; }",
        "        th { background-color: #f2f2f2; text-align: left; }",
        "        tr:nth-child(even) { background-color: #f9f9f9; }",
        "        .info-item { margin-bottom: 10px; }",
        "        .info-label { font-weight: bold; display: inline-block; width: 140px; }",
        "        .footer { margin-top: 30px; padding: 15px; background-color: #f2f2f2; border-radius: 5px; }",
        "        @media print { .container { box-shadow: none; } }",
        "    </style>",
        "</head>",
        "<body>",
        "    <div class='container'>",
        "        <h1>UAN Verification Details</h1>",
        "        <div class='info-item'>",
        f"            <span class='info-label'>UAN Number:</span> {data.get('UAN_Number', '')}",
        "        </div>",
        "        <div class='info-item'>",
        f"            <span class='info-label'>Name:</span> {data.get('First_Name', '')} {data.get('Last_Name', '')}",
        "        </div>",
        "        <h2>Employment History</h2>",
        "        <table>",
        "            <thead>",
        "                <tr>",
        "                    <th>Company Name</th>",
        "                    <th>Member ID</th>",
        "                    <th>Date of Joining</th>",
        "                    <th>Date of Exit</th>",
        "                    <th>Father/Husband Name</th>",
        "                </tr>",
        "            </thead>",
        "            <tbody>",
    ]

    for record in employment_records:
        html.extend([
            "                <tr>",
            f"                    <td>{record.get('Establishment Name', '')}</td>",
            f"                    <td>{record.get('MemberId', '')}</td>",
            f"                    <td>{record.get('Doj', '')}</td>",
            f"                    <td>{record.get('DateOfExitEpf', '')}</td>",
            f"                    <td>{record.get('father or Husband Name', '')}</td>",
            "                </tr>",
        ])

    html.extend([
        "            </tbody>",
        "        </table>",
        "        <div class='footer'>",
        "            <div class='info-item'>",
        f"                <span class='info-label'>Transaction ID:</span> {uan_verification.get('transId', '')}",
        "            </div>",
        "            <div class='info-item'>",
        f"                <span class='info-label'>TS Transaction ID:</span> {uan_verification.get('tsTransId', '')}",
        "            </div>",
        "        </div>",
        "    </div>",
        "</body>",
        "</html>",
    ])

    return "\n".join(html)
