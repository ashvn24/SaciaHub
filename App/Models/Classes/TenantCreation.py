from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi import status
from Models.db.db_connection import SessionLocal, engine
import logging

session = SessionLocal(bind=engine)


class SchemaManager:
    def __init__(self, shortname):
        self.shortname = shortname

    def create_schema_and_tables(self, schema_name):
        # try:
        # # Start a transaction
        #     with session.begin():
        create_schema_sql = text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

        session.execute(create_schema_sql)
        session.commit()

        tenant_table = f"tb_{self.shortname}_tenant_info"
        create_tenant_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{tenant_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "TenantUUID" UUID NOT NULL UNIQUE,
                    "TenantName" VARCHAR(255) NOT NULL,
                    "ShortName" VARCHAR(50),
                    "SchemaName" VARCHAR(255) NOT NULL,
                    "PortalURL" VARCHAR(255),
                    "TenantDetails" JSON,
                    "ContactName" VARCHAR(255),
                    "ContactEmail" VARCHAR(255),
                    "ContactPhoneNumber" VARCHAR(20),
                    "BillingContactName" VARCHAR(255),
                    "BillingContactEmail" VARCHAR(255),
                    "BillingContactPhoneNumber" VARCHAR(20),
                    "BillingAddressStreetName" VARCHAR(255),
                    "BillingAddressCity" VARCHAR(100),
                    "BillingAddressState" VARCHAR(100),
                    "BillingAddressCountry" VARCHAR(100),
                    "BillingAddressZipcode" VARCHAR(20),
                    "Licenses" JSON,
                    "ActiveModules" JSON,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON,
                    "FieldsValuesUpdated" JSON,
                    "TenantStatus" VARCHAR(255),
                    "Timesheets_Templates" VARCHAR(255)
                );
            """
        )
        session.execute(create_tenant_table_sql)
        # session.commit()

        client_table = f"tb_{self.shortname}_client_info"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{client_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "ClientID" VARCHAR(50) NOT NULL,
                "ClientUUID" UUID NOT NULL UNIQUE,
                "ClientName" VARCHAR(255) NOT NULL,
                "ClientShortName" VARCHAR(50),
                "VendorName" VARCHAR(255),
                "ClientContactName" VARCHAR(255),
                "WebsiteURL" VARCHAR(255),
                "ClientEIN" VARCHAR(50),
                "ClientContactFirstname" VARCHAR(255),
                "ClientContactLastname" VARCHAR(255),
                "ClientContactEmail" VARCHAR(255),
                "ClientContactPhoneNumber" VARCHAR(20),
                "ClientStreetName" VARCHAR(255),
                "ClientCity" VARCHAR(100),
                "ClientState" VARCHAR(100),
                "ClientCountry" VARCHAR(100),
                "ClientBillingContactNumber" VARCHAR(20),
                "ClientBillingContactFirstName" VARCHAR(255),
                "ClientBillingContactLastName" VARCHAR(255),
                "ClientBillingAppName" VARCHAR(255),
                "ClientBillingStreetName" VARCHAR(255),
                "ClientBillingCity" VARCHAR(100),
                "ClientBillingState" VARCHAR(100),
                "ClientBillingCountry" VARCHAR(100),
                "ClientBillingPhoneNumber" VARCHAR(20),
                "ClientBillingEmail" VARCHAR(255),
                "ClientBankName" VARCHAR(255),
                "ClientBankAccountNumber" VARCHAR(50),
                "ClientBankWireRoutingNumber" VARCHAR(50),
                "ClientBankACHRoutingNumber" VARCHAR(50),
                "ClientBankAddress" VARCHAR(255),
                "ClientStatus" VARCHAR(50),
                "ClientType" VARCHAR(50),
                "ClientEngagementType" JSON,
                "ClientProjectCount" INT,
                "ClientSOWCount" INT,
                "ClientBillableTotalHours" DECIMAL(10,2),
                "ClientBillablePayout" DECIMAL(10,2),
                "ClientBillableTotalRate" DECIMAL(10,2),
                "ClientBillableProfit" DECIMAL(10,2),
                "ClientProjectExpiryIn30Days" BOOLEAN,
                "ClientProjectExpiryIn60Days" BOOLEAN,
                "ClientProjectExpiryIn90Days" BOOLEAN,
                "ClientProjectExpiryIn180Days" BOOLEAN,
                "ClientImmigrationSupport" BOOLEAN,
                "ClientSecurityClearance" BOOLEAN,
                "ClientComplianceRequirement" JSON,
                "CreatedBy" UUID,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "FieldsUpdated" JSON,
                "FieldsValuesUpdated" JSON,
                "TenantUUID" UUID,
                "logo_url" VARCHAR(255),
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        table_name = f"tb_{self.shortname}_user_info"
        create_user_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{table_name}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "User_Id" VARCHAR(50),
                    "UserUUID" UUID NOT NULL UNIQUE,
                    "Username" VARCHAR(255),
                    "FirstName" VARCHAR(255),
                    "LastName" VARCHAR(255),
                    "Email" VARCHAR(255) NOT NULL,
                    "Password" VARCHAR(255) NOT NULL,
                    "PasswordLastSet" TIMESTAMP NULL,
                    "PasswordExpiry" TIMESTAMP NULL,
                    "PasswordPolicy" JSON DEFAULT '{{"minLength": 8, "specialCharRequired": true}}'::json,
                    "PhoneNumber" VARCHAR(20) NULL,
                    "Project" JSON,
                    "Client" JSON,
                    "SOW" JSON,
                    "Role" VARCHAR(50) NULL,
                    "Status" VARCHAR(50) DEFAULT 'Pending',
                    "UserGroup" JSON NULL,
                    "UserTeam" JSON NULL,
                    "AddressStreetName" VARCHAR(255) NULL,
                    "AddressCity" VARCHAR(100) NULL,
                    "AddressState" VARCHAR(100) NULL,
                    "AddressCountry" VARCHAR(100) NULL,
                    "Department" VARCHAR(255) NULL,
                    "JobTitle" VARCHAR(255) NULL,
                    "DateOfJoining" DATE NULL,
                    "LastLogin" TIMESTAMP NULL,
                    "ProfilePictureURL" VARCHAR(255) NULL,
                    "Skills" JSON NULL,
                    "ManagerUUID" UUID NULL,
                    "RequestedBy" UUID NULL,
                    "ApprovedBy" UUID NULL,
                    "RequestDateTime" TIMESTAMP NULL,
                    "ApprovedDateTime" TIMESTAMP NULL,
                    "User_manager" UUID NULL,
                    "User_ClientRep" UUID Null,
                    "TwoFactorAuth" VARCHAR(50),
                    "IsTwoFA" BOOLEAN DEFAULT FALSE,
                    "ClientUUID" UUID NULL,
                    "TenantUUID" UUID NULL,
                    "Timeoff_Policy" INT,
                    "Holiday_Policy" INT,
                    "Module" JSONB,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON NULL,
                    "FieldsValuesUpdated" JSON NULL,
                    "User_bgv" BOOLEAN DEFAULT FALSE,
                    "First_time_login" BOOLEAN DEFAULT TRUE,
                    "sso_active" BOOLEAN DEFAULT FALSE,
                    "otp" INTEGER,
                    "otp_created_at" TIMESTAMP,
                    authtoken VARCHAR(512) NULL,
                    twofa_expiry TIMESTAMP,
                    "HR_Manager" UUID NULL,
                    FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
                );
            """
        )
        session.execute(create_user_table_sql)
        # session.commit()

        project_table = f"tb_{self.shortname}_project_info"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{project_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "ProjectUUID" UUID NOT NULL UNIQUE,
                    "ClientUUID" UUID,
                    "ClientName" VARCHAR(255),
                    "VendorName" VARCHAR(255),
                    "VendorUUID" UUID,
                    "PartnerName" VARCHAR(255),
                    "PartnerUUID" UUID,
                    "ProjectName" VARCHAR(255) NOT NULL,
                    "ProjectTimesheetBuckets" JSON,
                    "UsersAssigned" JSON,
                    "ProjectStartDate" DATE,
                    "ProjectEndDate" DATE,
                    "ProjectStatus" VARCHAR(50),
                    "ProjectBudget" DECIMAL(15,2),
                    "ProjectSpent" DECIMAL(15,2),
                    "ProjectManager" VARCHAR(255),
                    "ProjectDescription" TEXT,
                    "ProjectType" VARCHAR(50),
                    "ProjectComplianceRequirements" JSON,
                    "CreatedBy" UUID,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON,
                    "FieldsValuesUpdated" JSON,
                    "TenantUUID" UUID,
                    "image_url" VARCHAR(255),
                    FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID"),
                    FOREIGN KEY ("ClientUUID") REFERENCES "{schema_name}"."{client_table}" ("ClientUUID") ON DELETE CASCADE
                );
            """
        )

        session.execute(create_table_sql)
        # session.commit()

        project_sow_table = f"tb_{self.shortname}_sow_info"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{project_sow_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "SOWUUID" UUID NOT NULL UNIQUE,
                    "ProjectUUID" UUID NOT NULL,
                    "ClientUUID" UUID,
                    "ClientName" VARCHAR(255),
                    "VendorUUID" UUID,
                    "VendorName" VARCHAR(255),
                    "PartnerUUID" UUID,
                    "PartnerName" VARCHAR(255),
                    "ProjectName" VARCHAR(255),
                    "ClientRepresentive" UUID,
                    "SOWName" VARCHAR(255) NOT NULL,
                    "SOWDescription" TEXT,
                    "SOWStartDate" DATE,
                    "SOWEndDate" DATE,
                    "SOWBudget" DECIMAL(15,2),
                    "SOWSpent" DECIMAL(15,2),
                    "SOWBillableRate" DECIMAL(10,2),
                    "SOWBillablePayout" DECIMAL(15,2),
                    "SOWStatus" VARCHAR(50),
                    "SOWComplianceRequirements" JSON,
                    "SOWAttachment" VARCHAR(255),
                    "UsersAssigned" JSON,
                    "SOWManagerUUID" UUID,
                    "CreatedBy" UUID,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON,
                    "FieldsValuesUpdated" JSON,
                    "TenantUUID" UUID,
                    FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID"),
                    FOREIGN KEY ("ProjectUUID") REFERENCES "{schema_name}"."{project_table}" ("ProjectUUID") ON DELETE CASCADE,
                    FOREIGN KEY ("ClientUUID") REFERENCES "{schema_name}"."{client_table}" ("ClientUUID") ON DELETE CASCADE
                );
            """
        )

        session.execute(create_table_sql)
        # session.commit()

        time_sheets = f"tb_{self.shortname}_timesheet"
        create_table_sql = text(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema_name}"."{time_sheets}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "TimesheetUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "TIMN" VARCHAR(50) ,
                "TIMD" VARCHAR(50) ,
                "UserUUID" UUID NOT NULL,
                "ClientUUID" UUID NULL,
                "ClientName" VARCHAR(255) NULL,
                "VendorName" VARCHAR(255) NULL,
                "ProjectUUID" UUID NULL,
                "ProjectName" VARCHAR(255) NULL,
                "SOWUUID" UUID NULL,
                "SOWName" VARCHAR(255) NULL,
                "User_Manager" VARCHAR(255) NULL,
                "StartDate" TIMESTAMP WITH TIME ZONE NULL,
                "EndDate" TIMESTAMP WITH TIME ZONE NULL,
                "Date" TIMESTAMP WITH TIME ZONE NULL,
                "Month" VARCHAR(20) NULL,
                "ProjectBucket" VARCHAR(255) NULL,
                "HoursWorked" DECIMAL(5,2) NULL,
                "WorkDescription" TEXT NULL,
                "Billable" BOOLEAN NULL,
                "Status" VARCHAR(50) NULL,
                "RejectionNotes" TEXT NULL,
                "RequestedBy" UUID NULL,
                "ApprovedBy" UUID NULL,
                "DeniedBy" UUID NULL,
                "TimesheetAttachmentURL" VARCHAR(255) NULL,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "FieldsUpdated" JSON NULL,
                "FieldsValuesUpdated" JSON NULL,
                "Latitude" VARCHAR(50),
                "Longitude" VARCHAR(50),
                "IPAddress" VARCHAR(50),
                "TenantUUID" UUID NULL,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID") ON DELETE CASCADE,
                FOREIGN KEY ("ProjectUUID") REFERENCES "{schema_name}"."{project_table}" ("ProjectUUID") ON DELETE SET NULL,
                FOREIGN KEY ("SOWUUID") REFERENCES "{schema_name}"."{project_sow_table}" ("SOWUUID") ON DELETE SET NULL,
                FOREIGN KEY ("ClientUUID") REFERENCES "{schema_name}"."{client_table}" ("ClientUUID") ON DELETE SET NULL,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        request_table = f"tb_{self.shortname}_requests"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{request_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "RequestUUID" UUID NOT NULL UNIQUE,
                    "REQN" VARCHAR(50),
                    "UserUUID" UUID NOT NULL,
                    "RequestType" VARCHAR(50) NULL,
                    "RequestDetails" JSON NULL,
                    "RequestAttachmentURL" VARCHAR(255) NULL,
                    "RequestDescription" VARCHAR(300) NULL,
                    "RequestStatus" VARCHAR(50) NULL,
                    "RequestPriority" VARCHAR(50) NULL,
                    "RequestedBy" UUID NULL,
                    "ApprovedBy" UUID NULL,
                    "DeniedBy" UUID NULL,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON NULL,
                    "FieldsValuesUpdated" JSON NULL,
                    "ApprovedByUUID" UUID NULL,
                    "ClientUUID" UUID NULL,
                    "TenantUUID" UUID NULL,
                    FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID") ON DELETE CASCADE,
                    FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID"),
                    FOREIGN KEY ("ClientUUID") REFERENCES "{schema_name}"."{client_table}" ("ClientUUID") ON DELETE SET NULL
                )
            """
        )

        session.execute(create_table_sql)
        # session.commit()

        tenant_settings = f"tb_{self.shortname}_tenant_settings"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{tenant_settings}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "TenantUUID" UUID NOT NULL,
                    "TimeOffTemplates" JSON,
                    "timesheet_notification" BOOLEAN,
                    "request_notification" BOOLEAN,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON,
                    "FieldsValuesUpdated" JSON,
                    FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
                );
            """
        )

        session.execute(create_table_sql)
        # session.commit()

        timeoff_table = f"tb_{self.shortname}_tenant_timeoff"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{timeoff_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "User_Name" VARCHAR(255) NOT NULL,
                    "Start_Date" DATE NOT NULL,
                    "End_Date" DATE NOT NULL,
                    "Hours" DECIMAL(5,2) NOT NULL,
                    "TeamName" VARCHAR(255) NOT NULL,
                    "Status" VARCHAR(50) NOT NULL,
                    "UserRole" VARCHAR(50) NOT NULL
                    )
                    """
        )
        session.execute(create_table_sql)
        # session.commit()

        vendor_table = f"tb_{self.shortname}_vendor_info"
        create_table_sql = text(
            f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}"."{vendor_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "VendorID" VARCHAR(50) NOT NULL,
                    "VendorUUID" UUID NOT NULL UNIQUE,
                    "VendorName" VARCHAR(255) NOT NULL,
                    "VendorContactName" VARCHAR(255),
                    "VendorManagerName" VARCHAR(255),
                    "WebsiteURL" VARCHAR(255),
                    "VendorEIN" VARCHAR(50),
                    "VendorContactFirstName" VARCHAR(255),
                    "VendorContactLastName" VARCHAR(255),
                    "VendorContactEmail" VARCHAR(255),
                    "VendorContactPhoneNumber" VARCHAR(20),
                    "VendorStreetName" VARCHAR(255),
                    "VendorCity" VARCHAR(100),
                    "VendorState" VARCHAR(100),
                    "VendorCountry" VARCHAR(100),
                    "VendorBillingContactNumber" VARCHAR(20),
                    "VendorBillingContactFirstName" VARCHAR(255),
                    "VendorBillingContactLastName" VARCHAR(255),
                    "VendorBillingAppName" VARCHAR(255),
                    "VendorBillingStreetName" VARCHAR(255),
                    "VendorBillingCity" VARCHAR(100),
                    "VendorBillingState" VARCHAR(100),
                    "VendorBillingCountry" VARCHAR(100),
                    "VendorBillingPhoneNumber" VARCHAR(20),
                    "VendorBillingEmail" VARCHAR(255),
                    "VendorBankName" VARCHAR(255),
                    "VendorBankAccountNumber" VARCHAR(50),
                    "VendorBankWireRoutingNumber" VARCHAR(50),
                    "VendorBankACHRoutingNumber" VARCHAR(50),
                    "VendorBankAddress" VARCHAR(255),
                    "ProjectAssigned" UUID,
                    "SOWAssigned" UUID,
                    "VendorStatus" VARCHAR(50),
                    "VendorType" VARCHAR(50),
                    "VendorEngagementType" JSON,
                    "VendorProjectCount" INT,
                    "VendorSOWCount" INT,
                    "VendorBillableTotalHours" DECIMAL(10,2),
                    "VendorBillablePayout" DECIMAL(10,2),
                    "VendorBillableTotalRate" DECIMAL(10,2),
                    "VendorBillableProfit" DECIMAL(10,2),
                    "VendorProjectExpiryIn30Days" BOOLEAN,
                    "VendorProjectExpiryIn60Days" BOOLEAN,
                    "VendorProjectExpiryIn90Days" BOOLEAN,
                    "VendorProjectExpiryIn180Days" BOOLEAN,
                    "VendorImmigrationSupport" BOOLEAN,
                    "VendorSecurityClearance" BOOLEAN,
                    "VendorComplianceRequirement" JSON,
                    "CreatedBy" UUID,
                    "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "FieldsUpdated" JSON,
                    "FieldsValuesUpdated" JSON,
                    "TenantUUID" UUID,
                    "logo_url" VARCHAR(255),
                    FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
                );
            """
        )

        session.execute(create_table_sql)
        # session.commit()

        bgv_table = f"tb_{self.shortname}_bgv_info"
        create_table_sql = text(
            f"""
                CREATE TABLE "{schema_name}"."{bgv_table}" (
                    "ID" BIGSERIAL PRIMARY KEY,
                    "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                    "UserUUID" UUID NOT NULL,
                    "IsFresher" BOOLEAN,
                    "IsUAN" BOOLEAN,
                    "isPassport" BOOLEAN,
                    "FirstName" VARCHAR(50),
                    "LastName" VARCHAR(50),
                    "MiddleName" VARCHAR(50),
                    "FatherName" VARCHAR(50),
                    "MobileNumber" VARCHAR(15),
                    "Date_of_Birth" DATE,
                    "Marital_Status" VARCHAR(50),
                    "Passport_Size_Photo" VARCHAR(255),
                    "Passport_Number" VARCHAR(255),
                    "Passport_Image" VARCHAR(255),
                    "Passport_FieldNumber" VARCHAR(255),
                    "UAN_Number" VARCHAR(255),
                    "PAN_Number" VARCHAR(255),
                    "PAN_Image" VARCHAR(255),
                    "Aadhar_Number" VARCHAR(255),
                    "Aadhar_Image" VARCHAR(255),
                    "CurrentAddress_Street" VARCHAR(255),
                    "CurrentAddress_City" VARCHAR(255),
                    "CurrentAddress_State" VARCHAR(50),
                    "CurrentAddress_Country" VARCHAR(50),
                    "CurrentAddress_PINcode" VARCHAR(50),
                    "PermanentAddress_Street" VARCHAR(50),
                    "PermanentAddress_City" VARCHAR(50),
                    "PermanentAddress_State" VARCHAR(50),
                    "PermanentAddress_Country" VARCHAR(50),
                    "PermanentAddress_PINcode" VARCHAR(50),
                    "Educational_Details" JSONB,
                    "Employment_Details" JSONB,
                    "status" VARCHAR(50) DEFAULT 'Pending',
                    "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "Selfie_Image" VARCHAR(255),
                    FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID") ON DELETE CASCADE
                    )
                """
        )
        session.execute(create_table_sql)
        # session.commit()

        bgv_results = f"tb_{self.shortname}_bgv_results"
        create_table_sql = text(
            f"""
                CREATE TABLE "{schema_name}"."{bgv_results}" (
                "Id" SERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL,
                "PAN_Verification" JSONB,
                "Aadhar_Verification" JSONB,
                "Passport_Verification" JSONB,
                "UAN_verification" JSONB,
                "Mobile_to_UAN" JSONB,
                "Criminal_check_Results" JSONB,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID") ON DELETE CASCADE
                )
                """
        )
        session.execute(create_table_sql)
        # session.commit()
        
        bgv_report_table = f"tb_{self.shortname}_bgv_report"
        create_table_sql = text(
            f"""
                CREATE TABLE "{schema_name}"."{bgv_report_table}" (
                "Id" SERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL,
                "ExecutiveSummary" JSONB,
                "Educational_Details" JSONB,
                "Employment_Details" JSONB,
                "IdentityDetails" JSONB,
                "CourtCheck" JSONB,
                "Drug_Check" JSONB,
                "Global_Database_Check" JSONB,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID") ON DELETE CASCADE
                )
                """
        )

        violation_table = f"tb_{self.shortname}_violations"
        create_table_sql = text(
            f"""
                CREATE TABLE "{schema_name}"."{violation_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL ,
                "Violation_Type" VARCHAR(50),
                "Violation_Description" VARCHAR(50),
                "Violation_Attachment_URL" VARCHAR(255),
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID")
                )
                """
        )
        session.execute(create_table_sql)
        # session.commit()

        notification_table = f"tb_{self.shortname}_notification"
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{notification_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "ToUUID" UUID NOT NULL,
                "FromUUID" UUID NOT NULL,
                "Notification_Type" VARCHAR(100),
                "Notification_SubType" VARCHAR(100),
                "Notification_Message" VARCHAR(255),
                "Notification_Expiry" TIMESTAMP WITH TIME ZONE NULL,
                "Notification_Read" BOOLEAN,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("ToUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID"),
                FOREIGN KEY ("FromUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID")
            )
        """
        )
        session.execute(create_table_sql)
        # session.commit()

        user_log_table = f"tb_{self.shortname}_tenant_Logs"
        create_table_sql = text(
            f"""
                CREATE TABLE "{schema_name}"."{user_log_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "LOGUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL,
                "TIMESTAMP" TIMESTAMP WITH TIME ZONE NULL,
                "HTTP_Method" VARCHAR(10),
                "End_Point" VARCHAR(255),
                "Request_Header" JSON,
                "Query_Parameters" JSON,
                "Request_Body" TEXT,
                "Response_Status_Code" INT,
                "Response_Body" TEXT,
                "User_ID" VARCHAR(255),
                "IP_Address" VARCHAR(55),
                "Response_Time" INT,
                "Error_Message" TEXT,
                "Error_Code" VARCHAR(50),
                "Auth_Token" TEXT,
                "Permissions" TEXT,
                "Session_ID" VARCHAR(255),
                "Request_Origin" VARCHAR(255),
                "Trace_ID" VARCHAR(255),
                "CustomData" JSON,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        holiday_table = f"tb_{self.shortname}_holidaypolicy"
        create_table_sql = text(
            f"""
                CREATE TABLE "{schema_name}"."{holiday_table}" (
                "ID" BIGSERIAL PRIMARY KEY, 
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "Template_Name" VARCHAR(50),
                "Template_Country" VARCHAR(50),
                "Holiday_Details" JSON,
                "HolidayAttachmentURL" VARCHAR(255),
                "TenantUUID" UUID,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
                );
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        timeoffpolicy_table = f"tb_{self.shortname}_timeoff_policy"
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{timeoffpolicy_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "Timeoff_Policy_Name" VARCHAR(50),
                "Timeoff_Country" VARCHAR(50),
                "Daily_Working_Hours" INT,
                "Monthly_Working_Hours" INT,
                "Yearly_Working_Hours" INT,
                "Yearly_Total_Hours" INT,
                "Timeoff_Details" JSONB,
                "TenantUUID" UUID,
                "Status" BOOLEAN DEFAULT True,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            )
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        timesheetpolicy_table = f"tb_{self.shortname}_timesheet_policy"
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{timesheetpolicy_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "Timesheet_template" VARCHAR(100),
                "Timesheet_fields" JSONB,
                "Timesheet_week_day_start" VARCHAR(50),
                "Timesheet_week_day_end" VARCHAR(50),
                "Timesheet_restrict_hours" INT,
                "Timesheet_min_restrict_hours" INT,
                "Timesheet_week_time_end" TIME,
                "Timesheet_month_end_day" BOOL,
                "Timesheet_month_day_time" TIME ,
                "Timesheet_month_rollover_days" INT,
                "TimesheetClient" VARCHAR(50),
                "TenantUUID" UUID,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            )
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        timesheetWeek_table = f"tb_{self.shortname}_timesheet_week"
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{timesheetWeek_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "TIMWID" VARCHAR(50) NOT NULL,
                "IDs" INTEGER[] NOT NULL,
                "UserUUID" UUID NOT NULL,
                "WeekStartDate" DATE NOT NULL,
                "WeekEndDate" DATE NOT NULL,
                "TotalHours" DECIMAL(5,2) NOT NULL,
                "Status" VARCHAR(50) NOT NULL,
                "ApprovedBy" UUID NULL,
                "ApprovedDateTime" TIMESTAMP NULL,
                "RejectedBy" UUID NULL,
                "RejectedDateTime" TIMESTAMP NULL,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "FieldsUpdated" JSON NULL,
                "FieldsValuesUpdated" JSON NULL,
                "TenantUUID" UUID NULL,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID"),
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            )
            """
        )
        session.execute(create_table_sql)
        # session.commit()

        timesheetMonth_table = f"tb_{self.shortname}_timesheet_month"
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{timesheetMonth_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL,
                "TIMMID" VARCHAR(50) NOT NULL,
                "IDs" INTEGER[] NOT NULL,
                "MonthStartDate" DATE NOT NULL,
                "MonthEndDate" DATE NOT NULL,
                "TotalHours" DECIMAL(5,2) NOT NULL,
                "Status" VARCHAR(50) NOT NULL,
                "ApprovedBy" UUID NULL,
                "ApprovedDateTime" TIMESTAMP NULL,
                "RejectedBy" UUID NULL,
                "RejectedDateTime" TIMESTAMP NULL,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "FieldsUpdated" JSON NULL,
                "FieldsValuesUpdated" JSON NULL,
                "TenantUUID" UUID NULL,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID"),
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            )
            """
        )
        session.execute(create_table_sql)
        # session.commit()
        
        partner_table = f"tb_{self.shortname}_partner_info"
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{partner_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "PartnerUUID" UUID NOT NULL UNIQUE,
                "PartnerName" VARCHAR(255) NOT NULL,
                "PartnerShortName" VARCHAR(50),
                "PartnerContactName" VARCHAR(255),
                "PartnerManagerName" VARCHAR(255),
                "WebsiteURL" VARCHAR(255),
                "PartnerEIN" VARCHAR(50),
                "PartnerContactFirstname" VARCHAR(255),
                "PartnerContactLastname" VARCHAR(255),
                "PartnerContactEmail" VARCHAR(255),
                "PartnerContactPhoneNumber" VARCHAR(20),
                "PartnerStreetName" VARCHAR(255),
                "PartnerCity" VARCHAR(100),
                "PartnerState" VARCHAR(100),
                "PartnerCountry" VARCHAR(100),
                "PartnerBillingContactNumber" VARCHAR(20),
                "PartnerBillingContactFirstName" VARCHAR(255),
                "PartnerBillingContactLastName" VARCHAR(255),
                "PartnerBillingAppName" VARCHAR(255),
                "PartnerBillingStreetName" VARCHAR(255),
                "PartnerBillingCity" VARCHAR(100),
                "PartnerBillingState" VARCHAR(100),
                "PartnerBillingCountry" VARCHAR(100),
                "PartnerBillingPhoneNumber" VARCHAR(20),
                "PartnerBillingEmail" VARCHAR(255),
                "PartnerBankName" VARCHAR(255),
                "PartnerBankAccountNumber" VARCHAR(50),
                "PartnerBankWireRoutingNumber" VARCHAR(50),
                "PartnerBankACHRoutingNumber" VARCHAR(50),
                "PartnerBankAddress" VARCHAR(255),
                "PartnerStatus" VARCHAR(50),
                "PartnerType" VARCHAR(50),
                "PartnerEngagementType" JSON,
                "PartnerProjectCount" INT,
                "PartnerSOWCount" INT,
                "PartnerBillableTotalHours" DECIMAL(10,2),
                "PartnerBillablePayout" DECIMAL(10,2),
                "PartnerBillableTotalRate" DECIMAL(10,2),
                "PartnerBillableProfit" DECIMAL(10,2),
                "PartnerProjectExpiryIn30Days" BOOLEAN,
                "PartnerProjectExpiryIn60Days" BOOLEAN,
                "PartnerProjectExpiryIn90Days" BOOLEAN,
                "PartnerProjectExpiryIn180Days" BOOLEAN,
                "PartnerImmigrationSupport" BOOLEAN,
                "PartnerSecurityClearance" BOOLEAN,
                "PartnerComplianceRequirement" JSON,
                "CreatedBy" UUID,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "FieldsUpdated" JSON,
                "FieldsValuesUpdated" JSON,
                "TenantUUID" UUID,
                "logo_url" VARCHAR(255),
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()
        
        folder_table = f'tb_{self.shortname}_folders'
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{folder_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "FolderUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "ParentFolderUUID" UUID,
                "EntityType" VARCHAR(50),
                "EntityUUID" UUID,
                "FolderName" VARCHAR(255) NOT NULL,
                "CreatedBy" UUID,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "TenantUUID" UUID,
                FOREIGN KEY ("ParentFolderUUID") REFERENCES "{schema_name}"."{folder_table}" ("FolderUUID"),
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
            )
        session.execute(create_table_sql)
        # session.commit()
        
        file_table =  f'tb_{self.shortname}_files'
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{file_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "FileUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "FolderUUID" UUID NOT NULL,
                "FileName" VARCHAR(255) NOT NULL,
                "FileContent" VARCHAR(50),
                "ContentType" VARCHAR(100),
                "CreatedBy" UUID,
                "CreationTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "UpdatedTimeAndDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "TenantUUID" UUID,
                FOREIGN KEY ("FolderUUID") REFERENCES "{schema_name}"."{folder_table}" ("FolderUUID") ON DELETE CASCADE,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()
        
        bgv_report_table = f'tb_{self.shortname}_bgv_report'
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{bgv_report_table}" (
                "Id" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL,
                "ExecutiveSummary" TEXT,
                "Educational_Details" JSONB,
                "Employment_Details" JSONB,
                "IdentityDetails" JSONB,
                "CourtCheck" JSONB,
                "Drug_Check" JSONB,
                "Global_Database_Check" JSONB,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "status" TEXT,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID")
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()
        
        salary_split_table = f'tb_{self.shortname}_salary_breakdown'
        create_table_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{salary_split_table}" (
                "ID" BIGSERIAL PRIMARY KEY,
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "UserUUID" UUID NOT NULL,
                "Amount_CTC" FLOAT,
                "Amount_PP_yearly" FLOAT,
                "Amount_CAb_allowance_yearly" FLOAT,
                "Amount_PF_Contribution_yearly" FLOAT,
                "Amount_Salary_After_Deductions_yearly" FLOAT,
                "Amount_Base_salary_yearly" FLOAT,
                "Amount_HRA_yearly" FLOAT,
                "Amount_Special_Allowances_yearly" FLOAT,
                "Amount_LTA_yearly" FLOAT,
                "Amount_Total_CTC_yearly" FLOAT,
                "Amount_Compensation_Package_yearly" FLOAT,
                "Amount_PP_Monthly" FLOAT,
                "Amount_CAb_allowance_Monthly" FLOAT,
                "Amount_PF_Contribution_Monthly" FLOAT,
                "Amount_Salary_After_Deductions_Monthly" FLOAT,
                "Amount_Base_salary_Monthly" FLOAT,
                "Amount_HRA_Monthly" FLOAT,
                "Amount_Special_Allowances_Monthly" FLOAT,
                "Amount_LTA_Monthly" FLOAT,
                "Amount_Total_CTC_Monthly" FLOAT,
                "Amount_Compensation_Package_Monthly" FLOAT,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("UserUUID") REFERENCES "{schema_name}"."{table_name}" ("UserUUID")
            );
            """
        )
        session.execute(create_table_sql)
        # session.commit()
        
        # salary_breakdown_settings = f'tb_{self.shortname}_salary_breakdown_settings'
        # create_table_sql = text(
        #     f"""
        #     CREATE TABLE "{schema_name}"."{salary_breakdown_settings}" (
        #         "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
        #         "ID" BIGSERIAL PRIMARY KEY,
        #         "TenantUUID" UUID NOT NULL,
        #         "Amount_PP" FLOAT NOT NULL, -- Fixed
        #         "Amount_CAb_allowance" FLOAT NOT NULL, -- Fixed
        #         "Amount_PF_Contribution" FLOAT NOT NULL, -- Fixed
        #         "Amount_Base_salary" FLOAT,
        #         "Amount_HRA" FLOAT,
        #         "Amount_Special_Allowances" FLOAT,
        #         "Amount_LTA" FLOAT,
        #         "Amount_Total_CTC" FLOAT,
        #         "Amount_Compensation_Package" FLOAT,
        #         "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #         FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
        #     );
        #     """
        # )
        # session.execute(create_table_sql)
        # session.commit()
        
        salary_deductions_settings = f'tb_{self.shortname}_salary_deductions_settings'
        create_salary_deductions_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{salary_deductions_settings}" (
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "ID" BIGSERIAL PRIMARY KEY,
                "TenantUUID" UUID NOT NULL,
                "Amount_PP" FLOAT NOT NULL DEFAULT 2400, -- Fixed default value
                "Amount_CAb_allowance" FLOAT NOT NULL DEFAULT 30000, -- Fixed default value
                "Amount_PF_Contribution" FLOAT NOT NULL DEFAULT 43200, -- Fixed default value
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
        )
        session.execute(create_salary_deductions_sql)
        # session.commit()
        
        salary_compensations = f'tb_{self.shortname}_salary_compensations'
        create_salary_compensations_sql = text(
            f"""
            CREATE TABLE "{schema_name}"."{salary_compensations}" (
                "TableUUID" UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
                "ID" BIGSERIAL PRIMARY KEY,
                "TenantUUID" UUID NOT NULL,
                "Amount_Base_salary" FLOAT DEFAULT 65,
                "Amount_HRA" FLOAT DEFAULT 12,
                "Amount_Special_Allowances" FLOAT DEFAULT 13,
                "Amount_LTA" FLOAT DEFAULT 10,
                "Created_date" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY ("TenantUUID") REFERENCES "{schema_name}"."{tenant_table}" ("TenantUUID")
            );
            """
        )
        session.execute(create_salary_compensations_sql)
        session.commit()

   