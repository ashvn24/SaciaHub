from collections import defaultdict
import io
import json
import logging
import uuid
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends
from fastapi.responses import JSONResponse
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from App.Models.Classes.UserManager import UserAuthManager
from App.Models.Classes.TenantCreation import SchemaManager
from Models.utils.send_mail import send_mail_func
from App.Models.Classes.token_authentication import (
    decode_token,
    generate_random_password,
    get_password_hash,
)
from Models.db.schemas import CustomerSchema, ResetPasswordSchema
from Models.db.db_connection import SessionLocal, engine
from Models.db import models
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.orm import Session
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


logger = logging.getLogger(__name__)

company_router = APIRouter(prefix="/v1/company", tags=["Company"])

session = SessionLocal(bind=engine)


@company_router.post("/register/")
async def create_customer_route(customer: CustomerSchema):
    try:
        user = (
            session.query(models.TenantInfo)
            .filter(models.TenantInfo.ContactEmail == customer.Contact_Email)
            .first()
        )
        if user is not None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Customer already exists"},
            )
        user = (
            session.query(models.TenantInfo)
            .filter(models.TenantInfo.ShortName == customer.Company_ShortName)
            .first()
        )
        if user is not None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Shortname already exists"},
            )

        new_customer = models.TenantInfo(
            TenantUUID=uuid.uuid4(),
            TenantName=customer.Company_Name,
            ContactName=f"{customer.Contact_FirstName} {
                customer.Contact_LastName}",
            ContactEmail=customer.Contact_Email,
            ContactPhoneNumber=customer.Contact_PhoneNumber,
            ShortName=customer.Company_ShortName,
            SchemaName=f"db_saciahub_sch_tenant_{customer.Company_ShortName}",
            PortalURL=f"{customer.Company_ShortName}.saciahub.com",
            TenantStatus="Requested",
        )

        session.add(new_customer)
        session.commit()
        session.refresh(new_customer)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Customer created successfully",
            },
        )

    except HTTPException as http_exc:
        raise http_exc  
    except SQLAlchemyError as sql_exc:
        session.rollback()  
        logger.error(f"Database error occurred: {str(sql_exc)}")
        raise sql_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        raise e


@company_router.post("/activate/")
async def activate_customer_route(Company_ShortName: str):

    try:

        user = (
            session.query(models.TenantInfo)
            .filter(models.TenantInfo.ShortName == Company_ShortName)
            .first()
        )

        if user is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Customer does not exist"},
            )

        if user.TenantStatus == "Active":
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Customer is already active"},
            )

        user.TenantStatus = "Active"
        # session.commit()

        schema_name = user.SchemaName
        print("schema", schema_name)
        shortname = user.ShortName

        manager = SchemaManager(shortname)
        manager.create_schema_and_tables(schema_name)
        session.commit()
        print("created")
        tenant_table = f"tb_{user.ShortName}_tenant_info"
        insert_tenant_table = f"{schema_name}.{tenant_table}"
        insert_query = text(
            f"""
                INSERT INTO {insert_tenant_table} ("TenantUUID", "TenantName", "ContactName","ContactEmail","ContactPhoneNumber",
                "ShortName", "SchemaName", "PortalURL", "TenantStatus")
                VALUES (:TenantUUID, :TenantName, :ContactName, :ContactEmail, :ContactPhoneNumber, :ShortName, :SchemaName,
                :PortalURL, :TenantStatus)
                """
        )
        session.execute(
            insert_query,
            {
                "TenantUUID": user.TenantUUID,
                "TenantName": user.TenantName,
                "ContactName": user.ContactName,
                "ContactEmail": user.ContactEmail,
                "ContactPhoneNumber": user.ContactPhoneNumber,
                "ShortName": user.ShortName,
                "SchemaName": user.SchemaName,
                "PortalURL": user.PortalURL,
                "TenantStatus": "Active",
            },
        )
        # session.commit()

        user_table_name = f"{user.SchemaName}.tb_{user.ShortName}_user_info"
        insert_query = text(
            f"""
                INSERT INTO {user_table_name} ("UserUUID", "User_Id", "Username", "FirstName", "LastName",
                "Email", "PhoneNumber", "Password", "Role", "TenantUUID", "User_bgv", "Module")
                VALUES (:UserUUID, :User_Id, :Username, :FirstName, :LastName, 
                :Email, :PhoneNumber, :Password, :Role, :TenantUUID, :User_bgv, :Module)
            """
        )
        # user_id = models.generate_unique_company_id()
        contact_name_parts = user.ContactName.split(" ")
        email = user.ContactEmail.lower()
        password = generate_random_password()
        session.execute(
            insert_query,
            {
                "UserUUID": uuid.uuid4(),
                "User_Id": models.generate_user_id(),
                "Username": contact_name_parts[0] + contact_name_parts[1],
                "FirstName": contact_name_parts[0],
                "LastName": contact_name_parts[1],
                "Email": email,
                "PhoneNumber": user.ContactPhoneNumber,
                "Password": get_password_hash(password),
                "Status": "Active",
                "Role": "Admin",
                "TenantUUID": user.TenantUUID,
                "User_bgv": True,
                "Module": json.dumps([
                                    "Applications",
                                    "Dashboard",
                                    "Requests",
                                    "TimeSheets",
                                    "Manage",
                                    "Reports",
                                    "Settings"
                                ])
            },
        )

        session.commit()

        select_query = text(
            f"""
            SELECT "Username", "FirstName", "Email", "Password"
            FROM {user_table_name}
            WHERE "Email" = :Email
            """
        )

        # Execute the select query
        result = session.execute(
            select_query, {"Email": user.ContactEmail}).fetchone()

        if result:
            FirstName = result.FirstName
            email = result.Email
            subject = "welcome"
            # Send email to the user
            send_mail_func(
                email,
                FirstName,
                password,
                subject,
                company_portal_url=Company_ShortName + ".saciahub.com",
            )
        else:
            print("User not found.")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Customer activated successfully"},
        )

    except SQLAlchemyError as e:
        session.rollback()
        return error.error(f"{str(e)}", 500, "Customer Activate Database Error")
    except Exception as e:
        return error.error(f"{str(e)}", 500, "Customer Activate")


@company_router.patch("/resetPassword/")
async def reset_password_route(data: ResetPasswordSchema, token_info = Depends(decode_token), db: Session = Depends(get_db)):
    try:
        user = (session.query(models.TenantInfo).filter(models.TenantInfo.PortalURL == data.Company_Shortname).first())
        if user is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Customer does not exist"},
            )
        user_table_name = f"{user.SchemaName}.tb_{user.ShortName}_user_info"
        user_query = text(f'SELECT * FROM {user_table_name} WHERE "Email" = :Username')
        user_result = session.execute(user_query, {"Username": data.Username})
        user_row = user_result.mappings().one_or_none()

        if user_row is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "User not found"},
            )
        if data.new_password != data.confirm_password:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "New password and confirm password do not match"},
            )
        new_password_hash = get_password_hash(data.new_password)
        update_query = text(
            f"""
            UPDATE {user_table_name}
            SET "Password" = :new_password_hash, "First_time_login" = :first_time_login, "Status" = :Status
            WHERE "Email" = :Username;
            """)
        session.execute(
            update_query,
            {
                "new_password_hash": new_password_hash,
                "Username": data.Username,
                "first_time_login": False,
                "Status": "Active"
            },
        )
        session.commit()
        portal =data.Company_Shortname
        auth = UserAuthManager(db, portal)
        if user_row.IsTwoFA == True:
            # Generate and send 2FA token
            two_fa_token = await auth.generate_2fa_token(user_row.Email, 'tfa')
            await auth.send_2fa_email(data.Username, two_fa_token)
            return {
                "message": "2FA verification required"
            }
        result = await auth._create_response(user_row, None)

        headers = {
            "Authorization": f"Bearer {result['access_token']}",
            "Refresh-Token": result['refresh_token'],
        }
        del result['access_token']
        del result['refresh_token']
        return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)

    except SQLAlchemyError as e:
        print(str(e))
        session.rollback()
        return error.error(f"{str(e)}", 500, "Reset Password Database Error")
    except Exception as e:
        print(str(e))
        return error.error(f"{str(e)}", 500, "Reset Password")
    finally:
        session.close()


@company_router.post("/createAccount/")
async def upload_csv(file: UploadFile = File(...)):
    contents = await file.read()

    # Read CSV file with multiple sheets
    excel_file = pd.ExcelFile(io.BytesIO(contents))

    client_data = None
    project_data = None

    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(io.BytesIO(contents), sheet_name=sheet_name)
        # print(sheet_name)

        if sheet_name == "tenant":
            tenant_data = df
        elif sheet_name == "Vendor":
            vendor_data = df
        elif sheet_name == "Clients":
            client_data = df
        elif sheet_name == "Projects":
            project_data = df
        elif sheet_name == "SOW":
            sow_data = df
        elif sheet_name == "Users":
            user_data = df
        elif sheet_name == "settings":
            settings_data = df
        elif sheet_name == "Violations":
            violations_data = df

    # for i in range(len(user_data)):
    #     print(
    #         user_data.SOW[i],
    #     )

    # return

    shortname = tenant_data["ShortName"][0]
    schemaname = f"db_saciahub_sch_tenant_{shortname}"

    try:
        if tenant_data is not None:
            for i in range(len(tenant_data)):
                new_customer = models.TenantInfo(
                    TenantUUID=uuid.uuid4(),
                    TenantName=tenant_data.TenantName[i],
                    ContactName=tenant_data.ContactName[i],
                    ContactEmail=tenant_data.ContactEmail[i],
                    ContactPhoneNumber=str(tenant_data.ContactPhoneNumber[i]),
                    TenantDetails=json.dumps(tenant_data.TenantDetails[i]),
                    BillingContactName=tenant_data.BillingContactName[i],
                    BillingContactEmail=tenant_data.BillingContactEmail[i],
                    BillingContactPhoneNumber=str(
                        tenant_data.BillingContactPhoneNumber[i]
                    ),
                    BillingAddressStreetName=tenant_data.BillingAddressStreetName[i],
                    BillingAddressCity=tenant_data.BillingAddressCity[i],
                    BillingAddressState=tenant_data.BillingAddressState[i],
                    BillingAddressCountry=tenant_data.BillingAddressCountry[i],
                    BillingAddressZipcode=str(
                        tenant_data.BillingAddressZipcode[i]),
                    ShortName=tenant_data.ShortName[i],
                    SchemaName=f"db_saciahub_sch_tenant_{
                        tenant_data.ShortName[i]}",
                    PortalURL=f"{tenant_data.ShortName[i]}.saciahub.com",
                    TenantStatus="Active",
                    Timesheets_Templates=tenant_data.Timesheets_Templates[i],
                )
                session.add(new_customer)
                session.commit()
                session.refresh(new_customer)

                manager = SchemaManager(shortname)
                manager.create_schema_and_tables(schemaname)

                tenant_table = f"tb_{shortname}_tenant_info"
                insert_tenant_table = f"{schemaname}.{tenant_table}"
                insert_query = text(
                    f"""
                    INSERT INTO {insert_tenant_table} ("TenantUUID", "TenantName", "TenantDetails", "ContactName","ContactEmail","ContactPhoneNumber",
                    "ShortName", "SchemaName", "PortalURL", "TenantStatus","BillingContactName","BillingContactEmail","BillingContactPhoneNumber","BillingAddressStreetName",
                    "BillingAddressCity","BillingAddressState","BillingAddressCountry","BillingAddressZipcode", "Timesheets_Templates")
                    VALUES (:TenantUUID, :TenantName, :TenantDetails, :ContactName, :ContactEmail, :ContactPhoneNumber, :ShortName, :SchemaName,
                    :PortalURL, :TenantStatus, :BillingContactName, :BillingContactEmail, :BillingContactPhoneNumber, :BillingAddressStreetName,
                    :BillingAddressCity, :BillingAddressState, :BillingAddressCountry, :BillingAddressZipcode, :Timesheets_Templates)
                    """
                )
                tenant_uuid = uuid.uuid4()
                logger.info("tenant", tenant_uuid)
                session.execute(
                    insert_query,
                    {
                        "TenantUUID": tenant_uuid,
                        "TenantName": tenant_data.TenantName[i],
                        "ContactName": tenant_data.ContactName[i],
                        "ContactEmail": tenant_data.ContactEmail[i],
                        "ContactPhoneNumber": str(tenant_data.ContactPhoneNumber[i]),
                        "ShortName": tenant_data.ShortName[i],
                        "SchemaName": f"db_saciahub_sch_tenant_{tenant_data.ShortName[i]}",
                        "TenantDetails": json.dumps(tenant_data.TenantDetails[i]),
                        "BillingContactName": tenant_data.BillingContactName[i],
                        "BillingContactEmail": tenant_data.BillingContactEmail[i],
                        "BillingContactPhoneNumber": str(
                            tenant_data.BillingContactPhoneNumber[i]
                        ),
                        "BillingAddressStreetName": tenant_data.BillingAddressStreetName[
                            i
                        ],
                        "BillingAddressCity": tenant_data.BillingAddressCity[i],
                        "BillingAddressState": tenant_data.BillingAddressState[i],
                        "BillingAddressCountry": tenant_data.BillingAddressCountry[i],
                        "BillingAddressZipcode": str(
                            tenant_data.BillingAddressZipcode[i]
                        ),
                        "PortalURL": f"{tenant_data.ShortName[i]}.saciahub.com",
                        "TenantStatus": "Active",
                        "Timesheets_Templates": tenant_data.Timesheets_Templates[i],
                    },
                )
                session.commit()

        if vendor_data is not None:
            vendor_table = f"tb_{shortname}_vendor_info"

            vendor_table_name = f"{schemaname}.{vendor_table}"
            for i in range(len(vendor_data)):
                insert_query = text(
                    f"""
                    INSERT INTO {vendor_table_name} ("VendorUUID", "VendorID", "VendorName", "VendorContactName", "WebsiteURL", "VendorEIN",
                    "VendorContactFirstname", "VendorContactLastname", "VendorContactEmail", "VendorContactPhoneNumber", "VendorStreetName",
                    "VendorCity", "VendorState", "VendorCountry", "VendorBillingContactNumber", "VendorBillingContactName", "VendorBillingAppName",
                    "VendorBillingStreetName", "VendorBillingCity", "VendorBillingState", "VendorBillingCountry", "VendorBillingPhoneNumber",
                    "VendorBillingEmail", "VendorStatus", "VendorType",
                    "VendorProjectExpiryIn30Days",
                    "VendorProjectExpiryIn60Days", "VendorProjectExpiryIn90Days", "VendorProjectExpiryIn180Days", "VendorImmigrationSupport",
                    "VendorSecurityClearance", "TenantUUID")
                    VALUES (:VendorUUID, :VendorID, :VendorName, :VendorContactName, :WebsiteURL, :VendorEIN, :VendorContactFirstname,
                    :VendorContactLastname, :VendorContactEmail, :VendorContactPhoneNumber, :VendorStreetName, :VendorCity, :VendorState,
                    :VendorCountry, :VendorBillingContactNumber, :VendorBillingContactName, :VendorBillingAppName, :VendorBillingStreetName,
                    :VendorBillingCity, :VendorBillingState, :VendorBillingCountry, :VendorBillingPhoneNumber, :VendorBillingEmail, :VendorStatus,
                    :VendorType, :VendorProjectExpiryIn30Days, :VendorProjectExpiryIn60Days, :VendorProjectExpiryIn90Days,
                    :VendorProjectExpiryIn180Days, :VendorImmigrationSupport, :VendorSecurityClearance, :TenantUUID)
                    """
                )
                vendor_uuid = uuid.uuid4()
                session.execute(
                    insert_query,
                    {
                        "VendorUUID": vendor_uuid,
                        "VendorID": models.generate_user_id(),
                        "VendorName": vendor_data.VendorName[i],
                        "VendorContactName": vendor_data.VendorContactName[i],
                        "WebsiteURL": vendor_data.WebsiteURL[i],
                        "VendorEIN": str(vendor_data.VendorEIN[i]),
                        "VendorContactFirstname": vendor_data.VendorContactFirstname[i],
                        "VendorContactLastname": vendor_data.VendorContactLastname[i],
                        "VendorContactEmail": vendor_data.VendorContactEmail[i],
                        "VendorContactPhoneNumber": str(
                            vendor_data.VendorContactPhoneNumber[i]
                        ),
                        "VendorStreetName": vendor_data.VendorStreetName[i],
                        "VendorCity": vendor_data.VendorCity[i],
                        "VendorState": vendor_data.VendorState[i],
                        "VendorCountry": vendor_data.VendorCountry[i],
                        "VendorBillingContactNumber": str(
                            vendor_data.VendorBillingContactNumber[i]
                        ),
                        "VendorBillingContactName": vendor_data.VendorBillingContactName[
                            i
                        ],
                        "VendorBillingAppName": vendor_data.VendorBillingAppName[i],
                        "VendorBillingStreetName": vendor_data.VendorBillingStreetName[
                            i
                        ],
                        "VendorBillingCity": vendor_data.VendorBillingCity[i],
                        "VendorBillingState": vendor_data.VendorBillingState[i],
                        "VendorBillingCountry": vendor_data.VendorBillingCountry[i],
                        "VendorBillingPhoneNumber": str(
                            vendor_data.VendorBillingPhoneNumber[i]
                        ),
                        "VendorBillingEmail": vendor_data.VendorBillingEmail[i],
                        "VendorStatus": vendor_data.VendorStatus[i],
                        "VendorType": str(vendor_data.VendorType[i]),
                        "VendorProjectExpiryIn30Days": (
                            True
                            if vendor_data.VendorProjectExpiryIn30Days[i] == "TRUE"
                            else False
                        ),
                        "VendorProjectExpiryIn60Days": (
                            True
                            if vendor_data.VendorProjectExpiryIn60Days[i] == "TRUE"
                            else False
                        ),
                        "VendorProjectExpiryIn90Days": (
                            True
                            if vendor_data.VendorProjectExpiryIn90Days[i] == "TRUE"
                            else False
                        ),
                        "VendorProjectExpiryIn180Days": (
                            True
                            if vendor_data.VendorProjectExpiryIn180Days[i] == "TRUE"
                            else False
                        ),
                        "VendorImmigrationSupport": (
                            True
                            if vendor_data.VendorImmigrationSupport[i] == "TRUE"
                            else False
                        ),
                        "VendorSecurityClearance": (
                            True
                            if vendor_data.VendorSecurityClearance[i] == "TRUE"
                            else False
                        ),
                        # "VendorComplianceRequirement": vendor_data.VendorComplianceRequirement[i],
                        "TenantUUID": tenant_uuid,
                    },
                )
                session.commit()

        if client_data is not None:
            # print(client_data.head())
            client_table = f"tb_{shortname}_client_info"

            client_table_name = f"{schemaname}.{client_table}"
            client_uuid_map = {}
            for i in range(len(client_data)):
                insert_query = text(
                    f"""
                    INSERT INTO {client_table_name} ("ClientUUID", "ClientID", "ClientName", "ClientContactName", "WebsiteURL",
                    "ClientEIN", "ClientContactFirstname", "ClientContactLastname", "ClientContactEmail", "ClientContactPhoneNumber",
                    "ClientStreetName", "ClientCity", "ClientState", "ClientCountry", "ClientBillingContactNumber", "ClientBillingContactName",
                    "ClientBillingAppName", "ClientBillingStreetName", "ClientBillingCity", "ClientBillingState", "ClientBillingCountry",
                    "ClientBillingPhoneNumber", "ClientBillingEmail", "ClientStatus", "ClientEngagementType",
                    "ClientBillableTotalHours", "ClientBillablePayout",
                    "ClientImmigrationSupport", "ClientSecurityClearance","TenantUUID")
                    VALUES (:ClientUUID, :ClientID, :ClientName, :ClientContactName, :WebsiteURL, :ClientEIN, :ClientContactFirstname,
                    :ClientContactLastname, :ClientContactEmail, :ClientContactPhoneNumber, :ClientStreetName, :ClientCity, :ClientState, :ClientCountry,
                    :ClientBillingContactNumber, :ClientBillingContactName, :ClientBillingAppName, :ClientBillingStreetName, :ClientBillingCity,
                    :ClientBillingState, :ClientBillingCountry, :ClientBillingPhoneNumber, :ClientBillingEmail, :ClientStatus,
                    :ClientEngagementType,:ClientBillableTotalHours, :ClientBillablePayout,
                    :ClientImmigrationSupport, :ClientSecurityClearance,:TenantUUID)
                    """
                )
                client_uuid = uuid.uuid4()
                session.execute(
                    insert_query,
                    {
                        "ClientUUID": client_uuid,
                        "ClientID": models.generate_user_id(),
                        "ClientName": client_data.ClientName[i],
                        "ClientContactName": client_data.ClientContactName[i],
                        "WebsiteURL": client_data.WebsiteURL[i],
                        "ClientEIN": str(client_data.ClientEIN[i]),
                        "ClientContactFirstname": client_data.ClientContactFirstname[i],
                        "ClientContactLastname": client_data.ClientContactLastname[i],
                        "ClientContactEmail": client_data.ClientContactEmail[i],
                        "ClientContactPhoneNumber": str(
                            client_data.ClientContactPhoneNumber[i]
                        ),
                        "ClientStreetName": client_data.ClientStreetName[i],
                        "ClientCity": client_data.ClientCity[i],
                        "ClientState": client_data.ClientState[i],
                        "ClientCountry": client_data.ClientCountry[i],
                        "ClientBillingContactNumber": str(
                            client_data.ClientBillingContactNumber[i]
                        ),
                        "ClientBillingContactName": client_data.ClientBillingContactName[
                            i
                        ],
                        "ClientBillingAppName": client_data.ClientBillingAppName[i],
                        "ClientBillingStreetName": client_data.ClientBillingStreetName[
                            i
                        ],
                        "ClientBillingCity": client_data.ClientBillingCity[i],
                        "ClientBillingState": client_data.ClientBillingState[i],
                        "ClientBillingCountry": client_data.ClientBillingCountry[i],
                        "ClientBillingPhoneNumber": str(
                            client_data.ClientBillingPhoneNumber[i]
                        ),
                        "ClientBillingEmail": client_data.ClientBillingEmail[i],
                        "ClientStatus": client_data.ClientStatus[i],
                        "ClientEngagementType": client_data.ClientEngagementType[i],
                        "ClientBillableTotalHours": float(
                            client_data.ClientBillableTotalHours[i]
                        ),
                        "ClientBillablePayout": float(
                            client_data.ClientBillablePayout[i]
                        ),
                        "ClientImmigrationSupport": (
                            True
                            if client_data.ClientImmigrationSupport[i] == "TRUE"
                            else False
                        ),
                        "ClientSecurityClearance": (
                            True
                            if client_data.ClientSecurityClearance[i] == "TRUE"
                            else False
                        ),
                        "TenantUUID": tenant_uuid,
                    },
                )
                session.commit()
                client_uuid_map[client_data.ClientName[i]] = client_uuid

        if project_data is not None:
            project_table_name = f"{schemaname}.tb_{shortname}_project_info"
            project_uuid_map = {}
            client_projects_map = defaultdict(list)

            for i in range(len(project_data)):
                client_name = project_data.ClientName[i]
                client_uuid = client_uuid_map.get(client_name)

                if client_uuid is None:
                    raise ValueError(
                        f"Client UUID not found for client name: {client_name}"
                    )

                insert_query = text(
                    f"""
                    INSERT INTO {project_table_name} ("ProjectUUID", "ClientUUID", "ClientName", "VendorName", "ProjectName",
                    "ProjectTimesheetBuckets", "ProjectStartDate", "ProjectEndDate", "ProjectStatus",
                    "ProjectBudget", "ProjectDescription", "ProjectType",
                    "ProjectComplianceRequirements", "TenantUUID")
                    VALUES (:ProjectUUID, :ClientUUID, :ClientName, :VendorName, :ProjectName, :ProjectTimesheetBuckets,
                    :ProjectStartDate, :ProjectEndDate, :ProjectStatus, :ProjectBudget, :ProjectDescription, :ProjectType,
                    :ProjectComplianceRequirements, :TenantUUID)
                    """
                )
                project_uuid = uuid.uuid4()

                # Handle NaN values
                project_budget = project_data.ProjectBudget[i]
                if pd.isna(project_budget):
                    project_budget = None
                else:
                    project_budget = float(project_budget)

                project_compliance = project_data.ProjectComplianceRequirements[i]
                if pd.isna(project_compliance):
                    project_compliance = json.dumps(None)
                else:
                    project_compliance = json.dumps(project_compliance)

                session.execute(
                    insert_query,
                    {
                        "ProjectUUID": project_uuid,
                        "ClientUUID": client_uuid,
                        "ClientName": project_data.ClientName[i],
                        "VendorName": (
                            project_data.VendorName[i]
                            if not pd.isna(project_data.VendorName[i])
                            else None
                        ),
                        "ProjectName": project_data.ProjectName[i],
                        "ProjectTimesheetBuckets": project_data.ProjectTimesheetBuckets[
                            i
                        ],
                        "ProjectStartDate": project_data.ProjectStartDate[i],
                        "ProjectEndDate": project_data.ProjectEndDate[i],
                        "ProjectStatus": project_data.ProjectStatus[i],
                        "ProjectBudget": project_budget,
                        "ProjectDescription": project_data.ProjectDescription[i],
                        "ProjectType": project_data.ProjectType[i],
                        "ProjectComplianceRequirements": project_compliance,
                        "TenantUUID": tenant_uuid,
                    },
                )
                session.commit()
                project_uuid_map[project_data.ProjectName[i]] = project_uuid
                client_projects_map[client_name].append(project_uuid)

                # print("client",client_projects_map)
        if sow_data is not None:
            table_name = f"tb_{shortname}_sow_info"

            sow_table_name = f"{schemaname}.tb_{shortname}_sow_info"
            sow_uuid_map = {}
            sow_to_projects = defaultdict(list)
            project_to_clients = defaultdict(str)

            for i in range(len(sow_data)):
                insert_query = text(
                    f"""
                    INSERT INTO {sow_table_name} ("SOWUUID", "ProjectUUID","ProjectName",
                    "SOWName", "SOWDescription", "SOWStartDate", "SOWEndDate", "SOWBudget", "SOWSpent", "SOWBillableRate",
                    "SOWBillablePayout", "SOWStatus", "SOWManagerUUID", "TenantUUID")
                    VALUES (:SOWUUID, :ProjectUUID,:ProjectName, :SOWName, :SOWDescription,
                    :SOWStartDate, :SOWEndDate, :SOWBudget, :SOWSpent, :SOWBillableRate, :SOWBillablePayout, :SOWStatus,
                     :SOWManagerUUID, :TenantUUID)
                    """
                )
                sow_uuid = uuid.uuid4()
                project_name = sow_data.ProjectName[i]
                session.execute(
                    insert_query,
                    {
                        "SOWUUID": sow_uuid,
                        "ProjectUUID": project_uuid_map.get(project_name),
                        "ProjectName": sow_data.ProjectName[i],
                        "SOWName": sow_data.SOWName[i],
                        "SOWDescription": sow_data.SOWDescription[i],
                        "SOWStartDate": sow_data.SOWStartDate[i],
                        "SOWEndDate": sow_data.SOWEndDate[i],
                        "SOWBudget": float(sow_data.SOWBudget[i]),
                        "SOWSpent": float(sow_data.SOWSpent[i]),
                        "SOWBillableRate": float(sow_data.SOWBillableRate[i]),
                        "SOWBillablePayout": float(sow_data.SOWBillablePayout[i]),
                        "SOWStatus": sow_data.SOWStatus[i],
                        "SOWManagerUUID": uuid.uuid4(),
                        "TenantUUID": tenant_uuid,
                    },
                )
                session.commit()
                sow_uuid_map[sow_data.SOWName[i]] = sow_uuid
                sow_to_projects[sow_data.SOWName[i]].append(project_name)
                project_to_clients[project_name] = project_data[
                    project_data.ProjectName == project_name
                ].ClientName.values[0]

        if user_data is not None:
            user_table_name = f"{schemaname}.tb_{shortname}_user_info"
            user_uuid_map = {}
            manager_uuid_map = {}
            client_rep_uuid_map = {}
            manager_assignment = {}
            client_rep_assignment = {}

            # First loop: Create UUIDs and set up assignments
            for i in range(len(user_data)):
                user_uuid = uuid.uuid4()
                user_uuid_map[user_data.Username[i]] = user_uuid
                if user_data.Role[i].lower() == "manager":
                    manager_uuid_map[user_data.Username[i]] = user_uuid
                    # Assign this manager to all users
                    for username in user_data.Username:
                        if username != user_data.Username[i]:
                            manager_assignment[username] = user_uuid
                elif user_data.Role[i].lower() == "clientrep":
                    client_rep_uuid_map[user_data.Username[i]] = user_uuid
                    # Assign this client rep to all users
                    for username in user_data.Username:
                        if username != user_data.Username[i]:
                            client_rep_assignment[username] = user_uuid

            # Second loop: Process and insert user data
            for i in range(len(user_data)):
                sow_list = json.loads(user_data.SOW[i])
                user_projects = []
                user_clients = set()

                for sow_name in sow_list.values():
                    print(sow_name)
                    projects = sow_to_projects.get(sow_name, [])
                    print("projects", projects)
                    user_projects.extend(projects)
                    for project in projects:
                        client = project_to_clients.get(project)
                        if client:
                            user_clients.add(client)

                user_projects = list(set(user_projects))  # Remove duplicates
                user_clients = list(user_clients)  # Convert set to list

                # Assign manager and client rep UUIDs
                user_manager_uuid = manager_assignment.get(
                    user_data.Username[i])
                user_client_rep_uuid = client_rep_assignment.get(
                    user_data.Username[i])

                insert_query = text(
                    f"""
                    INSERT INTO {user_table_name} ("UserUUID", "User_Id", "Username", "FirstName", "LastName", "Email", "PhoneNumber", "Password",
                    "SOW", "Role", "Project", "Client", "Status", "UserGroup", "UserTeam", "AddressStreetName", "AddressCity", "AddressState", "AddressCountry",
                    "Department", "JobTitle", "DateOfJoining", "ProfilePictureURL", "Skills",
                    "RequestDateTime", "ApprovedDateTime","User_ClientRep", "User_manager", "User_bgv")
                    VALUES (:UserUUID, :User_Id, :Username, :FirstName, :LastName, :Email, :PhoneNumber, :Password,
                    :SOW, :Role, :Project, :Client, :Status, :UserGroup, :UserTeam, :AddressStreetName, :AddressCity, :AddressState, :AddressCountry,
                    :Department, :JobTitle, :DateOfJoining, :ProfilePictureURL, :Skills,
                    :RequestDateTime, :ApprovedDateTime, :User_ClientRep, :User_manager, :User_bgv)
                """
                )
                session.execute(
                    insert_query,
                    {
                        "UserUUID": user_uuid_map[user_data.Username[i]],
                        "User_Id": models.generate_user_id(),
                        "Username": user_data.Username[i],
                        "FirstName": user_data.FirstName[i],
                        "LastName": user_data.LastName[i],
                        "Email": user_data.Email[i],
                        "PhoneNumber": str(user_data.PhoneNumber[i]),
                        "Password": get_password_hash(user_data.Password[i]),
                        "Project": json.dumps(user_projects),
                        "Client": json.dumps(user_clients),
                        "Status": "Active",
                        "Role": user_data.Role[i],
                        "SOW": json.dumps(sow_list),
                        "UserGroup": json.dumps(user_data.UserGroup[i]),
                        "UserTeam": json.dumps(user_data.UserTeam[i]),
                        "AddressStreetName": user_data.AddressStreetName[i],
                        "AddressCity": user_data.AddressCity[i],
                        "AddressState": user_data.AddressState[i],
                        "AddressCountry": user_data.AddressCountry[i],
                        "Department": user_data.Department[i],
                        "JobTitle": user_data.JobTitle[i],
                        "DateOfJoining": user_data.DateOfJoining[i],
                        "ProfilePictureURL": user_data.ProfilePictureURL[i],
                        "Skills": json.dumps(user_data.Skills[i]),
                        "RequestDateTime": user_data.RequestDateTime[i],
                        "ApprovedDateTime": user_data.ApprovedDateTime[i],
                        "User_bgv": True if user_data.User_bgv[i] == "TRUE" else False,
                        "User_manager": user_manager_uuid,
                        "User_ClientRep": user_client_rep_uuid,
                        "TenantUUID": tenant_uuid,
                    },
                )
                session.commit()
                user_uuid_map[user_data.Username[i]] = user_uuid

        if settings_data is not None:
            settings_table_name = f"{schemaname}.tb_{
                shortname}_tenant_settings"
            for i in range(len(settings_data)):
                insert_query = text(
                    f"""
                    INSERT INTO {settings_table_name} ("TenantUUID", "TimeOffTemplates")
                    VALUES (:TenantUUID, :TimeOffTemplates)
                    """
                )
                session.execute(
                    insert_query,
                    {
                        "TenantUUID": tenant_uuid,
                        "TimeOffTemplates": json.dumps(
                            settings_data.TimeOffTemplates[i]
                        ),
                    },
                )
                session.commit()

        if violations_data is not None:
            violations_table_name = f"{schemaname}.tb_{shortname}_violations"
            insert_query = text(
                f"""
                INSERT INTO {violations_table_name} ("UserUUID", "Violation_Type", "Violation_Description", "Violation_Attachment_URL")
                VALUES (:UserUUID, :Violation_Type, :Violation_Description, :Violation_Attachment_URL)
                """
            )

            session.execute(
                insert_query,
                {
                    "UserUUID": uuid.uuid4(),
                    "Violation_Type": violations_data.Violation_Type[i],
                    "Violation_Description": violations_data.Violation_Description[i],
                    "Violation_Attachment_URL": violations_data.Violation_Attachment_URL[
                        i
                    ],
                },
            )
            session.commit()

    except PendingRollbackError as e:
        session.rollback()
        print(f"Pending rollback error: {e}")
    except SQLAlchemyError as e:
        session.rollback()
        raise e
    except Exception as e:
        raise e
    finally:
        session.close()

    return {"message": "CSV file processed successfully"}
