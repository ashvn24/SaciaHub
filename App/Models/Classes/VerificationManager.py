from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
import json

from App.Models.Classes.token_authentication import decrypt_data, encrypt_data
from Models.db.Verification import Aadhar_Verify, Criminal_Verification, PAN_Verification, Passport_Verify, UAN_Verification
from Models.db.schemas import verification
from Models.db.models import User_bgv
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()

class Verification:
    def __init__(self, db: Session, data: verification, token_info):
        self.db = db
        self.data = data
        self.token_info = token_info
        self.user = None

    @property
    def encrypted_fields(self):
        return ["Passport_Number", "Passport_FieldNumber", "UAN_Number","PAN_Number","Aadhar_Number"]
    
    async def get_user(self):
        query = select(User_bgv)
        filters = []
        
        if self.data.First_Name:
            filters.append(User_bgv.First_Name.ilike(self.data.First_Name))
        if self.data.Last_Name:
            filters.append(User_bgv.Last_Name.ilike (self.data.Last_Name))
        if self.data.Date_of_Birth:
            filters.append(User_bgv.Date_of_Birth == self.data.Date_of_Birth.strftime('%Y-%m-%d'))
        if self.data.UAN:
            filters.append(User_bgv.UAN_Number == encrypt_data(self.data.UAN))
        if filters:
            query = query.filter(*filters)
        
        self.user = self.db.execute(query).scalars().first()
        usrdata = self.user.__dict__
        usrdata.pop("_sa_instance_state", None)
        encrypted_fields = self.encrypted_fields
        for field in encrypted_fields:
            if field in usrdata and usrdata[field]:
                usrdata[field] = decrypt_data(usrdata[field])
        print(usrdata)
        return usrdata

    def verify_document(self, verifier, document, error_message):
        if document:
            verification_result = json.loads(verifier().verify(document))
            print(verification_result)
            if verification_result and verification_result.get("status") != 1:
                return error.error(error_message, 400, "Bad Request")
            return verification_result

    def verify_pan(self):
        return self.verify_document(PAN_Verification, self.data.pan, "PAN Verification Failed")

    def verify_aadhar(self):
        return self.verify_document(Aadhar_Verify, self.data.Aadhar, "Aadhar Verification Failed")

    def verify_uan(self):
        return self.verify_document(UAN_Verification, self.data.UAN, "UAN Verification Failed")

    def verify_passport(self):
        if self.data.passport:
            passport_verification = Passport_Verify().verify(self.data.passport, self.data.Date_of_Birth)
            if passport_verification and passport_verification.get("status") != 1:
                return error.error("Passport Verification Failed", 400, "Bad Request")
            return passport_verification

    def verify_criminal_check(self):
        if self.data.Address:
            address_str = f"{self.data.Address.Street}, {self.data.Address.city}, {self.data.Address.state}, {self.data.Address.pin}, {self.data.Address.country}"
            full_name = f"{self.data.First_Name} {self.data.Last_Name}"
            criminal_check_results = Criminal_Verification().verify(full_name, address_str)
            if criminal_check_results and criminal_check_results.get("status") != 1:
                return error.error("Criminal Check Verification Failed", 400, "Bad Request")
            return criminal_check_results

    async def update_user(self):
        if self.user:
            self.user.PAN_Verification = self.verify_pan() if self.data.pan and (not self.user.PAN_Verification or not self.user.PAN_Number) else self.user.PAN_Verification
            self.user.PAN_Number = self.data.pan if self.data.pan else self.user.PAN_Number

            self.user.Aadhar_Verification = self.verify_aadhar() if self.data.Aadhar and (not self.user.Aadhar_Verification or not self.user.Aadhar_Number) else self.user.Aadhar_Verification
            self.user.Aadhar_Number = self.data.Aadhar if self.data.Aadhar else self.user.Aadhar_Number

            self.user.UAN_Verification = self.verify_uan() if self.data.UAN and (not self.user.UAN_Verification or not self.user.UAN_Number) else self.user.UAN_Verification
            self.user.UAN_Number = self.data.UAN if self.data.UAN else self.user.UAN_Number

            self.user.Passport_Verification = self.verify_passport() if self.data.passport and (not self.user.Passport_Verification or not self.user.Passport_Number) else self.user.Passport_Verification
            self.user.Passport_Number = self.data.passport if self.data.passport else self.user.Passport_Number

            self.user.Criminal_check_Results = self.verify_criminal_check() if self.data.Address and not self.user.Criminal_check_Results else self.user.Criminal_check_Results

            self.db.commit()
            return {"message": "User information updated successfully"}

    async def create_user(self):
        pan_verification = self.verify_pan()
        aadhar_verification = self.verify_aadhar()
        uan_verification = self.verify_uan()
        passport_verification = self.verify_passport()
        criminal_check_results = self.verify_criminal_check()

        if not self.user and uan_verification:
            self.extractor(uan_verification)
            
        encrypted_pan, encrypted_aadhar, encrypted_uan, encrypted_passport = self.encryptor()

        new_user = User_bgv(
            First_Name=self.data.First_Name,
            Last_Name=self.data.Last_Name,
            Date_of_Birth=self.data.Date_of_Birth.strftime('%Y-%m-%d') if self.data.Date_of_Birth else None,
            PAN_Number=encrypted_pan,
            Aadhar_Number=encrypted_aadhar,
            UAN_Number=encrypted_uan,
            Passport_Number=encrypted_passport,
            PAN_Verification=pan_verification,
            Aadhar_Verification=aadhar_verification,
            UAN_Verification=uan_verification,
            Passport_Verification=passport_verification,
            Criminal_check_Results=criminal_check_results
        )

        self.db.add(new_user)
        self.db.commit()
        return {"message": f"Verification completed successfully for {self.data.First_Name} {self.data.Last_Name}"}

    def encryptor(self):
        encrypted_pan = encrypt_data(self.data.pan) if self.data.pan else None
        encrypted_aadhar = encrypt_data(self.data.Aadhar) if self.data.Aadhar else None
        encrypted_uan = encrypt_data(self.data.UAN) if self.data.UAN else None
        encrypted_passport = encrypt_data(self.data.passport) if self.data.passport else None
        return encrypted_pan,encrypted_aadhar,encrypted_uan,encrypted_passport

    def extractor(self, uan_verification):
        if uan_verification:
            try:
                if isinstance(uan_verification, str):
                    uan_verification = json.loads(uan_verification)
                if isinstance(uan_verification, dict) and "msg" in uan_verification and uan_verification["msg"]:
                    full_name = uan_verification["msg"][0]["name"]
                    self.data.First_Name, self.data.Last_Name = full_name.split(" ", 1)
            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
                print(f"Error processing UAN verification: {e}")

    async def process(self):
        if self.token_info["role"] not in ["Admin", "Manager"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You do not have the permission to perform this action"
            )
        if self.data.Date_of_Birth and self.data.First_Name and self.data.Last_Name:
            await self.get_user()
        if self.user:
            return await self.update_user()
        return await self.create_user()
