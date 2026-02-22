import json
from datetime import datetime, date
from uuid import UUID
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError
from prettytable import PrettyTable



def make_serializable(data):
    if isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_serializable(item) for item in data]
    elif isinstance(data, (datetime, date, UUID)):
        return str(data)  # Convert date, datetime, and UUID to string
    else:
        return data
    
def process_user_data(data):
    excluded_keys = {"TABLEUUID", "ID", "UserUUID", "Created_date"}
    processed_data = {key: value for key, value in data.items() if key not in excluded_keys}
    
    for key, value in processed_data.items():
        if isinstance(value, str):
            try:
                processed_data[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    
    return format_uan_data_as_table(processed_data)

def serialize_non_null_data(user):
    if isinstance(user, dict):  # If it's already a dictionary, return it as is
        return process_user_data({k: v for k, v in user.items() if v is not None})
    
    try:
        return process_user_data({
            attr.key: getattr(user, attr.key)
            for attr in class_mapper(type(user)).attrs
            if getattr(user, attr.key) is not None
        })
    except UnmappedClassError:
        raise ValueError("Provided object is not an ORM-mapped instance")
    
def format_uan_data_as_table(json_data):
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            return "<html><body><p>Error: Invalid JSON data provided</p></body></html>"
    else:
        data = json_data
    
    # Extract UAN verification data
    uan_verification = data.get("UAN_Verification", {})
    employment_records = uan_verification.get("msg", [])
    
    # Create a complete HTML page
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html lang='en'>")
    html.append("<head>")
    html.append("    <meta charset='UTF-8'>")
    html.append("    <meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    html.append("    <title>UAN Verification Details</title>")
    html.append("    <style>")
    html.append("        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }")
    html.append("        .container { max-width: 900px; margin: 0 auto; background: #fff; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }")
    html.append("        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }")
    html.append("        h2 { color: #2c3e50; margin-top: 30px; }")
    html.append("        table { width: 100%; border-collapse: collapse; margin: 20px 0; }")
    html.append("        th, td { padding: 12px 15px; border: 1px solid #ddd; }")
    html.append("        th { background-color: #f2f2f2; text-align: left; }")
    html.append("        tr:nth-child(even) { background-color: #f9f9f9; }")
    html.append("        .info-item { margin-bottom: 10px; }")
    html.append("        .info-label { font-weight: bold; display: inline-block; width: 140px; }")
    html.append("        .footer { margin-top: 30px; padding: 15px; background-color: #f2f2f2; border-radius: 5px; }")
    html.append("        @media print { .container { box-shadow: none; } }")
    html.append("    </style>")
    html.append("</head>")
    html.append("<body>")
    html.append("    <div class='container'>")
    
    # Header section
    html.append("        <h1>UAN Verification Details</h1>")
    html.append("        <div class='info-item'>")
    html.append(f"            <span class='info-label'>UAN Number:</span> {data.get('UAN_Number', '')}")
    html.append("        </div>")
    html.append("        <div class='info-item'>")
    html.append(f"            <span class='info-label'>Name:</span> {data.get('First_Name', '')} {data.get('Last_Name', '')}")
    html.append("        </div>")
    
    # Employment history table
    html.append("        <h2>Employment History</h2>")
    html.append("        <table>")
    html.append("            <thead>")
    html.append("                <tr>")
    html.append("                    <th>Company Name</th>")
    html.append("                    <th>Member ID</th>")
    html.append("                    <th>Date of Joining</th>")
    html.append("                    <th>Date of Exit</th>")
    html.append("                    <th>Father/Husband Name</th>")
    html.append("                </tr>")
    html.append("            </thead>")
    html.append("            <tbody>")
    
    # Table rows
    for record in employment_records:
        html.append("                <tr>")
        html.append(f"                    <td>{record.get('Establishment Name', '')}</td>")
        html.append(f"                    <td>{record.get('MemberId', '')}</td>")
        html.append(f"                    <td>{record.get('Doj', '')}</td>")
        html.append(f"                    <td>{record.get('DateOfExitEpf', '')}</td>")
        html.append(f"                    <td>{record.get('father or Husband Name', '')}</td>")
        html.append("                </tr>")
    
    html.append("            </tbody>")
    html.append("        </table>")
    
    # Transaction details
    html.append("        <div class='footer'>")
    html.append("            <div class='info-item'>")
    html.append(f"                <span class='info-label'>Transaction ID:</span> {uan_verification.get('transId', '')}")
    html.append("            </div>")
    html.append("            <div class='info-item'>")
    html.append(f"                <span class='info-label'>TS Transaction ID:</span> {uan_verification.get('tsTransId', '')}")
    html.append("            </div>")
    html.append("        </div>")
    
    html.append("    </div>")
    html.append("</body>")
    html.append("</html>")
    
    return "\n".join(html)