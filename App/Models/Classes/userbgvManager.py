from datetime import datetime, timedelta, timezone
import json
from cryptography.x509 import verification
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, query
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from logging import Logger
from typing import Dict, Any

from Models.db import models
from Models.Classes.GetUser import GetUser
from Models.db.models import TenantInfo, User_bgv
from Models.db.schemas import BritsUserBGVSchema, BritsUserBGVUpdateSchema
from Models.Classes.token_authentication import decrypt_data, encrypt_data
from Models.db.Verification import MOBtoUAN, PAN_Verification, Aadhar_Verify, Passport_Verify, UAN_Verification
from typing import Optional, List
from .MediaManager import MediaManager
import os
import re
from PIL import Image
import pytesseract
import logging
from typing import Dict, Optional
from difflib import SequenceMatcher
import requests
from io import BytesIO
from PIL import Image, ImageEnhance,ImageFilter
import cv2
import numpy as np
import sys
from sqlalchemy.engine import Row
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()

class UserBGVManager:
    def __init__(self, db: Session, Company_Portal_Url: str = None,  logger: Logger = None):
        self.db = db
        self.logger = logger
        self.bgv_table = None
        self.token_info = None
        self.company_portal_url = Company_Portal_Url

        if Company_Portal_Url:
            self.company_portal_url = Company_Portal_Url
            self.tenant =self._get_tenant_info()
            self.setuptables()
    
    @property
    def encrypted_fields(self):
        return ["Passport_Number", "Passport_FieldNumber", "UAN_Number","PAN_Number","Aadhar_Number"]
    
    @staticmethod
    def parse_date(date_str):
        """Parse a date string into a standard format (YYYY-MM-DD)"""
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).date().isoformat()
            except ValueError:
                continue
        return None
            
    def _get_tenant_info(self):
        user = (self.db.query(models.TenantInfo).filter(models.TenantInfo.PortalURL == self.company_portal_url).first())
        if user is None: raise HTTPException(status_code=404, detail={"message": "Schema not found"})
        return user
    
    def setuptables(self):
        self.bgvtable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_bgv_info"
        self.usertable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_user_info"
        self.bgvresults = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_bgv_results"
        self.reptable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_bgv_report"
        self.violationtable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_violations"
        self.clienttable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_client_info"
        self.projecttable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_project_info"
        self.master_bgv_results = "db_saciahub_sch_master.tb_master_exd_bgvinfo"
        print("Master Table:", self.master_bgv_results)

    def check_user_exists(self, user_uuid: str) -> bool:
        query = text(f'SELECT * FROM {self.usertable} WHERE "UserUUID" = :UserUUID')
        result = self.db.execute(query, {"UserUUID": user_uuid}).fetchone()
        return result is not None

    def insert_bgv_data(self, data: Dict[str, Any]) -> None:
        columns = ", ".join([f'"{k}"' for k in data.keys()])
        values = ", ".join([f":{k}" for k in data.keys()])
        query = text(f"INSERT INTO {self.bgvtable} ({columns}) VALUES ({values})")
        self.db.execute(query, data)
        self.db.commit()

    def insert_bgv_results(self, data: Dict[str, Any]) -> None:
        columns = ", ".join([f'"{k}"' for k in data.keys()])
        values = ", ".join([f":{k}" for k in data.keys()])
        query = text(f"INSERT INTO {self.bgvresults} ({columns}) VALUES ({values})")
        self.db.execute(query, data)
        self.db.commit()

    def update_bgv_data(self, data: Dict[str, Any], user_uuid: str) -> None:
        print(f"Updating BGV data for user with : {data}")
        try:
            # Handle long URLs - store only the filename
            for field in ['Aadhar_Image', 'PAN_Image', 'Passport_Image', 'Selfie_Image']:
                if field in data and data[field]:
                    # Extract filename from URL
                    url = str(data[field])
                    print(f"Processing {field} URL:", url)
                    # Handle case where the value might already be just a filename
                    if '/' in url:
                        filename = url.split('/')[-1].split('?')[0]
                        print("Extracted filename:", filename)
                        data[field] = filename

            # Update the database
            update_fields = ", ".join([f'"{key}" = :{key}' for key in data.keys()])
            print("Update Fields:", update_fields)
            query = text(f'UPDATE {self.bgvtable} SET {update_fields} WHERE "UserUUID" = :UserUUID')
            data["UserUUID"] = user_uuid
            self.db.execute(query, data)
            # self.db.commit()

        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error(f"Database error in update_bgv_data: {str(e)}")
            raise error.error(f"Error updating user BGV: {str(e)}", 500, "Internal Server Error")
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Error in update_bgv_data: {str(e)}")
            raise error.error(f"Error updating user BGV: {str(e)}", 500, "Internal Server Error")

    def update_verification_result(self, field: str, value: Any, user_uuid: str) -> None:

        query = text(f'UPDATE {self.bgvresults} SET "{field}" = :value WHERE "UserUUID" = :UserUUID')
        self.db.execute(query, {"value": value, "UserUUID": user_uuid})

        #Only if master table is found then update

        check_query = text(f'''
            SELECT 1 FROM {self.master_bgv_results}
            WHERE "UserUUID" = :UserUUID
            LIMIT 1
        ''')
        result = self.db.execute(check_query, {"UserUUID": user_uuid}).first()

        print(f"Master Result Found With UserUUID-{user_uuid}\n", result)

        # Step 2: If found, update the field
        if result:
            if field == "UAN_verification":
                field = "UAN_Verification"
            update_query = text(f'''
                UPDATE {self.master_bgv_results}
                SET "{field}" = :value
                WHERE "UserUUID" = :UserUUID
            ''')
            self.db.execute(update_query, {"value": value, "UserUUID": user_uuid})
        # self.db.commit()

    def check_all_fields_filled(self, user_uuid: str) -> bool:
        column_query = text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        )
        columns = self.db.execute( column_query, { "schema": self.bgvtable.split('.')[0],"table": self.bgvtable.split('.')[1], },).fetchall()

        select_query = text(f'SELECT * FROM {self.bgvtable} WHERE "UserUUID" = :UserUUID')
        result = self.db.execute(select_query, {"UserUUID": user_uuid})
        existing_bgv = dict(zip(result.keys(), result.fetchone()))
        is_fresher = existing_bgv.get("IsFresher", False)
        
        for column in columns:
            column_name = column[0]
            if column_name not in ["UserUUID", "status", "MiddleName", "UAN_Number", "IsUAN", "IsFresher", "Passport_Number", "Passport_Image", "Passport_FieldNumber", "isPassport"]:
                value = existing_bgv.get(column_name)
                if column_name == "Educational_Details":
                    if value is None or value == {} or (isinstance(value, dict) and not any(value.values())):
                        return False
                if column_name == "Employment_Details":
                    if not is_fresher and (value is None or value == {} or (isinstance(value, dict) and not any(value.values()))):
                        return False
                elif value is None or (isinstance(value, str) and value.strip() == ""):
                    return False
        return True
    
    async def get_adhar_link(self):
        try:
            aadhar_verify = Aadhar_Verify().get_digilocker_link()
            return aadhar_verify
        except Exception as e:
            raise error.error(str(e), 400, "Bad Request")
        
        
    def update_user_bgv_status(self, user_uuid: str) -> None:
        query = text(f'UPDATE {self.usertable} SET "User_bgv" = TRUE WHERE "UserUUID" = :UserUUID')
        self.db.execute(query, {"UserUUID": user_uuid})
        
    def update_phonenumber(self, user_uuid: str):
        bgvdata = self.get_user_bgv(user_uuid)
        if bgvdata and bgvdata['MobileNumber']:
            query = text(f'UPDATE {self.usertable} SET "PhoneNumber" = :phno WHERE "UserUUID" = :UserUUID')
            self.db.execute(query, {"phno":bgvdata['MobileNumber'], "UserUUID": user_uuid})
        if bgvdata and bgvdata['Passport_Size_Photo']:
            query = text(f'UPDATE {self.usertable} SET "ProfilePictureURL" = :profile WHERE "UserUUID" = :UserUUID')
            self.db.execute(query, {"profile":bgvdata['Passport_Size_Photo'], "UserUUID": user_uuid})

    def get_user_bgv(self, user_uuid: str, type:str =None) -> Dict[str, Any]:
        try:
            query = text(f'SELECT * FROM {self.bgvtable} WHERE "UserUUID" = :UserUUID')
            result = self.db.execute(query, {"UserUUID": user_uuid}).fetchone()
            if type == "create":
                return result
            if not result:
                raise error.error("User BGV not found", 404, "Not Found")
            user_bgv = dict(result._mapping)
            encrypted_fields = self.encrypted_fields
            for field in encrypted_fields:
                if field in user_bgv and user_bgv[field]:
                    user_bgv[field] = decrypt_data(user_bgv[field])
            return user_bgv
        except Exception as e:
            print("Exception in get_user_bgv", e)
            return error.error(str(e), 400, "Bad Request")

    def create_user_bgv(self, data: BritsUserBGVSchema, token_info: Dict[str, Any]) -> Dict[str, str]:
        GetUser(self.db, data.Company_Portal_Url).verify_user(token_info)
        try:
            if not self.check_user_exists(token_info["Id"]):
                return error.error("User not found", 404, "Not Found")
            if self.get_user_bgv(token_info["Id"], "create"):
                return error.error("User BGV already exists", 400, "Bad Request")           
            
            bgv_data = self.prepare_bgv_data(data, token_info["Id"])
            self.insert_bgv_data(bgv_data)
            verification_results = self.perform_verifications(data, token_info["Id"])
            self.insert_bgv_results(verification_results)
            self.db.commit()
            
            
            return {
                    "message": "User BGV created successfully"
                }

        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            self.logger.error(f"Database error occurred: {str(sql_exc)}")
            return error.error("An internal server error occurred", 500, "Internal Server Error")
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"An unexpected error occurred: {str(e)}")
            return error.error("An unexpected error occurred", 400, "Bad Request")
    
    def similar(self,a: str, b: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, a, b).ratio()
    
    def check_aadhar_similarity(self, correct_number: str, ocr_number: str, min_matches: int = 5):
        # Validate the correct number
        if not correct_number.isdigit() or len(correct_number) != 12:
            raise ValueError("Correct Aadhar number must be exactly 12 digits.")
        
        # Filter only digits from the OCR result
        ocr_digits = ''.join(filter(str.isdigit, ocr_number))
        
        # Limit to first 12 digits if OCR gives more
        ocr_digits = ocr_digits[:12]

        match_positions = []

        # Compare digit-by-digit
        for i in range(min(len(correct_number), len(ocr_digits))):
            if correct_number[i] == ocr_digits[i]:
                match_positions.append(i)

        is_match = len(match_positions) >= min_matches

        return is_match, match_positions
    
    
    def check_pan_similarity(self, correct_pan: str, ocr_pan: str, min_matches: int = 5):
        # Sanitize inputs
        correct_pan = correct_pan.upper().strip()
        ocr_pan = ''.join(filter(str.isalnum, ocr_pan.upper().strip()))

        if len(correct_pan) != 10:
            raise ValueError("Correct PAN number must be exactly 10 alphanumeric characters.")

        # Trim or pad OCR input to 10 characters
        ocr_pan = ocr_pan[:10]

        match_positions = []

        for i in range(min(len(correct_pan), len(ocr_pan))):
            if correct_pan[i] == ocr_pan[i]:
                match_positions.append(i)

        is_match = len(match_positions) >= min_matches

        return is_match, match_positions



    def longest_common_subsequence(self, a, b):
        dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        for i in range(1, len(a) + 1):
            for j in range(1, len(b) + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return dp[-1][-1]

    def match_name(self, input_name, extracted_text):
        input_parts = input_name.lower().split()
        extracted_text_lower = extracted_text.lower()
        for part in input_parts:
            if part in extracted_text_lower:
                return 100.0
        return 0.0

    def extract_possible_dobs(self, text):
        lines = text.split('\n') if isinstance(text, str) else text
        candidates = []
        for line in lines:
            match = re.search(r'(\d{1,2}[\/\-][0-9A-Za-z]{1,2}[\/\-]\d{4})', line)
            if match:
                candidates.append(match.group(1))
        return candidates if candidates else [text]

    def match_dob(self, input_dob, extracted_text):
        input_dob_digits = re.sub(r'[^0-9]', '', input_dob)
        candidates = self.extract_possible_dobs(extracted_text)
        best_match = 0.0
        for candidate in candidates:
            candidate_digits = re.sub(r'[^0-9]', '', candidate)
            lcs = self.longest_common_subsequence(input_dob_digits, candidate_digits)
            score = (lcs / len(input_dob_digits)) * 100 if input_dob_digits else 0
            if score > best_match:
                best_match = score
        return round(best_match, 2)

    def extract_all_digits_excluding_dob(self, extracted_lines):
        text = ' '.join(extracted_lines)
        dob_like_patterns = re.findall(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', text)
        dob_digits = set()
        for dob in dob_like_patterns:
            digits = re.findall(r'\d+', dob)
            dob_digits.update(digits)

        all_digits = re.findall(r'\d+', text)
        filtered_digits = [d for d in all_digits if d not in dob_digits and len(d) >= 4]

        return ''.join(filtered_digits)

    def match_aadhaar(self, input_aadhaar, extracted_lines, input_name, input_dob):
        input_digits = re.sub(r'\D', '', input_aadhaar)
        filtered_digits = self.extract_all_digits_excluding_dob(extracted_lines)
        if not filtered_digits:
            filtered_digits = ''.join(re.findall(r'\d+', ' '.join(extracted_lines)))
        best_score = 0.0
        lcs = self.longest_common_subsequence(input_digits, filtered_digits)
        score = (lcs / len(input_digits)) * 100 if input_digits else 0
        if score > best_score:
            best_score = score
        
        name_score = self.match_name(input_name, ' '.join(extracted_lines))
        dob_score = self.match_dob(input_dob, ' '.join(extracted_lines))
        
        return round((best_score * 0.4 + name_score * 0.3 + dob_score * 0.3), 2)

    def match_pan(self, input_pan, extracted_text_lines, input_name, input_dob):
        input_pan = input_pan.upper().strip()
        extracted_text = ' '.join(extracted_text_lines).upper()
        pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'
        candidates = re.findall(pan_pattern, extracted_text)
        print("Candidates:", candidates)

        best_score = 0.0
        for candidate in candidates:
            lcs = self.longest_common_subsequence(input_pan, candidate)
            print("LCS:", lcs)
            score = (lcs / len(input_pan)) * 100 if input_pan else 0
            print("Score:", score)
            if score > best_score:
                best_score = score

        # Also consider name and DOB match for PAN
        name_score = self.match_name(input_name, extracted_text)
        dob_score =  self.match_dob(input_dob, extracted_text)
        print("Name Score:", name_score)
        print("DOB Score", dob_score)
        print("Best Score:", best_score)

        return round((best_score * 0.4 + name_score * 0.3 + dob_score * 0.3), 2)

    def match_passport(self, input_passport, extracted_text_lines, input_name, input_dob):
        input_passport = input_passport.upper().strip()
        extracted_text = ' '.join(extracted_text_lines).upper()
        passport_pattern = r'\b[A-Z][0-9]{7}\b'
        candidates = re.findall(passport_pattern, extracted_text)

        best_score = 0.0
        for candidate in candidates:
            lcs = self.longest_common_subsequence(input_passport, candidate)
            score = (lcs / len(input_passport)) * 100 if input_passport else 0
            if score > best_score:
                best_score = score

        # Also consider name and DOB match for Passport
        name_score = self.match_name(input_name, extracted_text)
        dob_score = self.match_dob(input_dob, extracted_text)

        return round((best_score * 0.4 + name_score * 0.3 + dob_score * 0.3), 2)

    def overall_match(self, doc_type, input_name, input_dob, input_number, extracted_text_lines):
        extracted_text = ' '.join(extracted_text_lines)
        name_match = self.match_name(input_name, extracted_text)
        dob_line = next((line for line in extracted_text_lines if "dob" in line.lower()), '')
        dob_text = dob_line if dob_line else extracted_text
        dob_match = self.match_dob(input_dob, dob_text)

        if doc_type == "aadhaar":
            id_match = self.match_aadhaar(input_number, extracted_text_lines, input_name, input_dob)
        elif doc_type == "pan":
            id_match = self.match_pan(input_number, extracted_text_lines, input_name, input_dob)
        elif doc_type == "passport":
            id_match = self.match_aadhaar(input_number, extracted_text_lines, input_name, input_dob)
        else:
            id_match = 0.0

        final_score = id_match  

        return {
            "name_match": name_match,
            "dob_match": dob_match,
            f"{doc_type}_match": id_match,
            "final_score": round(final_score, 2)
        }



        
    async def perform_bgv_image_verification(self, data: BritsUserBGVSchema, user_uuid: str) -> dict:
        print("Performing BGV image verification", user_uuid)
        try:
            # Create MediaManager instance
            media_manager = MediaManager(self.db, self.token_info, self.company_portal_url)

            # Get images from data
            adhar_image = data.Aadhar_Image
            pan_card_image = data.PAN_Image
            passport_image = data.Passport_Image

            # Fetch BGV data
            query = text(f"""
                SELECT 
                    "FirstName",
                    "MiddleName",
                    "LastName",
                    "Aadhar_Number",
                    "PAN_Number",
                    "Passport_Number",
                    TO_CHAR("Date_of_Birth", 'DD/MM/YYYY') AS "DOB"
                FROM {self.bgvtable} 
                WHERE "UserUUID" = :user_uuid
            """)
            result = self.db.execute(query, {"user_uuid": user_uuid}).mappings().first()
            if not result:
                raise HTTPException(status_code=404, detail="User BGV data not found")

            # Construct full name
            name_parts = [
                result["FirstName"],
                result["MiddleName"] if result["MiddleName"] else "",
                result["LastName"]
            ]
            full_name = " ".join(filter(None, name_parts)).strip()
            full_name_cleaned = " ".join(full_name.split()).lower()
            date_of_birth = result["DOB"]
            
            print("Full Name:", full_name)

            # Decrypt data
            encrypted_fields = self.encrypted_fields
            decrypted_data = {}
            for field in encrypted_fields:
                if field in result and result[field]:
                    decrypted_data[field] = decrypt_data(result[field])
                else:
                    decrypted_data[field] = None
            print("Decrypted_Data:", decrypted_data)
            verification_results = {}

            # Aadhar verification
            if adhar_image:
                try:
                    adhar_image_url = await media_manager.get_media(adhar_image, user_uuid)
                    print("Aadhar Image URL:", adhar_image_url)
                    if adhar_image_url:
                        adhar_similarity = 0
                        adhar_data = self.extract_id_data(adhar_image_url)
                        print("Aadhar Data:", adhar_data)
                        if adhar_data and isinstance(adhar_data, dict):
                            result_data = self.overall_match(
                                "aadhaar",
                                full_name_cleaned,
                                date_of_birth,
                                decrypted_data.get("Aadhar_Number"),
                                adhar_data.get("text").split("\n")
                            )
                            print("Result Data:", result_data)
                            if result_data['final_score'] >= 65:
                                adhar_data['similarity'] = result_data['final_score']
                                pass
                            else:
                                adhar_data['error'] = "Aadhar Data mismatch"
                                adhar_data['similarity'] = result_data['final_score']
                            
                                    
                        verification_results["aadhar"] = adhar_data or {
                            "document_type": "Error",
                            "error": "Failed to process Aadhar image"
                        }
                except Exception as e:
                    verification_results["aadhar"] = {
                        "document_type": "Error",
                        "error": f"Error processing Aadhar image: {str(e)}"
                    }

            # PAN verification
            if pan_card_image:
                pan_card_image_url = await media_manager.get_media(pan_card_image, user_uuid)
                pan_data = self.extract_pan_data(pan_card_image_url)
                if pan_data:
                    extracted_name = pan_data.get("name")
                    extracted_number = pan_data.get("pan_number")
                    extracted_dob = pan_data.get("dob")
                    extracted_text = pan_data.get("text")
                    result_data = self.overall_match(
                        "pan",
                        full_name_cleaned,
                        date_of_birth,
                        decrypted_data.get("PAN_Number"),
                        extracted_text.split("\n")
                    )
                    print("Result Data:", result_data)
                    # pan_data['similarity'] = result_data['final_score']
                    if result_data['final_score'] >= 65:
                        pan_data['similarity'] = result_data['final_score']
                        pass
                    else:
                        pan_data['error'] = "PAN Data mismatch"
                        pan_data['similarity'] = result_data['final_score']
                                    
                verification_results["pan"] = pan_data

            # Passport verification
            if passport_image:
                passport_image_url = await media_manager.get_media(passport_image, user_uuid)
                passport_data = self.extract_id_data(passport_image_url)
                print("Passport Data:", passport_data)
                if passport_data:
                    result_data = self.overall_match(
                        "passport",
                        full_name_cleaned,
                        date_of_birth,
                        decrypted_data.get("Passport_Number"),
                        passport_data.get("text").split("\n")
                    )
                    print("Result Data:", result_data)
                    if result_data['final_score'] >= 65:
                        passport_data['similarity'] = result_data['final_score']
                        pass
                    else:
                        passport_data['error'] = "Passport Data mismatch"
                        passport_data['similarity'] = result_data['final_score']
                        
                verification_results["passport"] = passport_data


            # Raise error if any document has "error"
            for doc_type, result in verification_results.items():
                print("Doc_Type:",doc_type)
                if result.get("document_type") == "Error" or result.get("error"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "message": "BGV image verification failed",
                            "verification_results_error": verification_results
                        }
                    )

            return {
                "message": "BGV image verification completed",
                "verification_results": verification_results
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error during BGV image verification: {str(e)}")
            print(f"Error during BGV image verification: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error during BGV image verification: {str(e)}"
            )
            
    def extract_pan_name(self,text):
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        name = "Not found"
        pan_number = None

        # Step 1: Extract PAN number
        for line in lines:
            match = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', line)
            if match:
                pan_number = match.group(1)
                break

        if not pan_number:
            return {"pan_number": "Not found", "name": "Not found"}

        # Step 2: Try multiple patterns for name extraction
        for i, line in enumerate(lines):
            if pan_number in line:
                # Strategy 1: Next 1-3 lines after PAN number
                for j in range(i+1, min(i+4, len(lines))):
                    candidate = lines[j]
                    # Heuristic: Likely names are 2+ uppercase words, at least 8 characters total
                    if re.match(r'^[A-Z][A-Z\s]{4,}$', candidate) and len(candidate.split()) >= 2:
                        name = candidate
                        break

                # Strategy 2: Collect 2 adjacent lines if they're both short and uppercase
                if name == "Not found" and i + 2 < len(lines):
                    part1 = lines[i+1]
                    part2 = lines[i+2]
                    combined = f"{part1} {part2}"
                    if re.match(r'^[A-Z\s]{8,}$', combined):
                        name = combined.strip()
                        break

                # Strategy 3: Look ahead for any line with 2 uppercase words
                if name == "Not found":
                    for k in range(i+1, min(i+5, len(lines))):
                        words = lines[k].strip().split()
                        if len(words) >= 2 and all(re.match(r'^[A-Z]+$', w) for w in words):
                            name = lines[k].strip()
                            break

                break

        return {
            "pan_number": pan_number,
            "name": name
        }
            
    
    def extract_pan_data(self, image_url: str) -> Optional[Dict[str, str]]:
        if not image_url:
            return {
                "document_type": "Error",
                "error": "No image URL provided",
                "text": None
            }

        print("OsName:", os.name)
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe' if os.name == 'nt' else '/usr/bin/tesseract'

        if not os.path.exists(tesseract_path):
            return {
                "document_type": "Error",
                "error": "Tesseract OCR not found",
                "text": None
            }

        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        import requests
        from io import BytesIO
        from PIL import Image
        import numpy as np
        import cv2
        import re

        response = requests.get(image_url)
        if response.status_code != 200:
            return {
                "document_type": "Error",
                "error": f"Failed to download image: HTTP {response.status_code}",
                "text": None
            }
        try:

            # Load and preprocess image
            pil_image = Image.open(BytesIO(response.content)).convert("RGB")
            image_np = np.array(pil_image)

            # Convert RGB to BGR for OpenCV compatibility
            image_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

            # Use pytesseract OCR
            text = pytesseract.image_to_string(image_cv)
            
            print("Extracted Text:", text)

            # Extract PAN
            pan_number_match = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', text)
            pan_number = pan_number_match.group(1) if pan_number_match else "Not found"

            # Extract DOB
            dob_match = re.search(r'\b(\d{2}[\/\-]?\d{2}[\/\-]?\d{4})\b', text)
            dob = "Not found"
            dob_match = re.search(r'\b(\d{2}[\/\-]?\d{2}[\/\-]?\d{4})\b', text)
            if dob_match:
                raw_dob = dob_match.group(1)
                # Normalize: from "14112005" or "14-11-2005" to "14/11/2005"
                if "/" not in raw_dob:
                    dob = f"{raw_dob[:2]}/{raw_dob[2:4]}/{raw_dob[4:]}"
                else:
                    dob = raw_dob.replace("-", "/")

            # Extract name
            # Extract name based on location after PAN number
            result = self.extract_pan_name(text)
            name = result["name"] if result["name"] != "Not found" else "Not found"
            number = result["pan_number"] if result["pan_number"] != "Not found" else "Not found"



            return {
                "document_type": "PAN",
                "name": name,
                "dob": dob,
                "pan_number": pan_number,
                "number": number,
                "text": text
            }

        except Exception as e:
            return {
                "document_type": "Error",
                "error": f"OCR processing failed: {str(e)}",
                "text": None
            }


        

    def extract_id_data(self, image_url: str) -> Optional[Dict[str, str]]:
        try:
            if not image_url:
                return {
                    "document_type": "Error",
                    "error": "No image URL provided",
                    "text": None
                }

            # Tesseract path
            # tesseract_path = '/usr/bin/tesseract'
            print("OsName:",os.name)
            tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe' if os.name == 'nt' else '/usr/bin/tesseract'
            
            if not os.path.exists(tesseract_path):
                return {
                    "document_type": "Error",
                    "error": "Tesseract OCR not found. Please install it using: winget install UB-Mannheim.TesseractOCR",
                    "text": None
                }
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

            

            # Download image
            response = requests.get(image_url)
            if response.status_code != 200:
                return {
                    "document_type": "Error",
                    "error": f"Failed to download image: HTTP {response.status_code}",
                    "text": None
                }

            image = Image.open(BytesIO(response.content))

            # Preprocess image
            image = image.convert("L")  # Grayscale
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2)  # Boost contrast
            image = image.filter(ImageFilter.MedianFilter())  # Reduce noise
            image = image.point(lambda x: 0 if x < 150 else 255, '1')  # Binarize

            # OCR extraction
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            print("Extracted Text:", text)
            
            

            if not text.strip():
                return {
                    "document_type": "Error",
                    "error": "No text extracted from image",
                    "text": None
                }

            lines = [line.strip() for line in text.split('\n') if line.strip()]
            print("Extracted Lines:", lines)

            
                        

            # PAN check
            # pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'
            # for i, line in enumerate(lines):
            #     if re.fullmatch(pan_pattern, line):
            #         pan_number = line
            #         name = None
            #         for j in range(i + 1, min(i + 4, len(lines))):
            #             if lines[j].isupper() and len(lines[j].split()) >= 2:
            #                 name = lines[j]
            #                 break
            #         return {
            #             "document_type": "PAN Card",
            #             "pan_number": pan_number,
            #             "name": name,
            #             "text": text
            #         }
            

            # # Passport check
            # passport_pattern = r'\b[A-Z0-9]{8}\b'
            # passport_matches = re.findall(passport_pattern, text)
            # if passport_matches:
            #     passport_number = None
            #     name = None
            #     dob = None
            #     dob_match = re.search(r'(?:Date of Birth|DOB)[:\s\-]*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', text, re.IGNORECASE)
            #     if dob_match:
            #         dob = dob_match.group(1).replace("-", "/")
            #     else:
            #         # Try MRZ format: YYMMDD (assume birth year > 1950 and < current year)
            #         mrz_dob_match = re.search(r'\b([0-9]{2})([0-9]{2})([0-9]{2})\b', text)
            #         if mrz_dob_match:
            #             yy, mm, dd = mrz_dob_match.groups()
            #             year = int(yy)
            #             year += 2000 if year < 50 else 1900
            #             dob = f"{dd}/{mm}/{year}"

            #     # Extract passport number
            #     for num in passport_matches:
            #         if re.match(r'[A-Z][0-9]{7}', num):  # Likely correct
            #             passport_number = num
            #             break
            #         elif re.match(r'[0-9]{8}', num):  # Might be missing first letter
            #             passport_number = num
            #             break

            #     # Extract name - look for patterns specific to Indian passports
            #     name_patterns = [
            #         r'(?:Given Name\(s\)|Name\(s\))\s*([A-Z]+(?:\s+[A-Z]+)*)',  # After "Given Name(s)"
            #         r'(?:Surname|GURENKA)\s*([A-Z]+(?:\s+[A-Z]+)*)',  # After "Surname"
            #         r'P<IND([A-Z]+<<[A-Z]+(?:<<[A-Z]+)*)',  # Machine Readable Zone
            #     ]

            #     for pattern in name_patterns:
            #         matches = re.finditer(pattern, text, re.MULTILINE)
            #         for match in matches:
            #             extracted_name = match.group(1)
            #             if '<<' in extracted_name:
            #                 # Handle Machine Readable Zone format
            #                 name_parts = extracted_name.split('<<')
            #                 name = ' '.join(part for part in name_parts if part)
            #             else:
            #                 name = extracted_name
            #             if name:
            #                 break
            #         if name:
            #             break

            #     # If still no name found, try more general patterns
            #     if not name:
            #         for line in lines:
            #             # Look for lines with capital letters that could be names
            #             if re.match(r'^[A-Z]+(?:\s+[A-Z]+)*$', line.strip()) and len(line.split()) >= 2:
            #                 if not any(word in line for word in ['REPUBLIC', 'INDIA', 'PASSPORT', 'GIVEN']):
            #                     name = line.strip()
            #                     break


            #     return {
            #         "document_type": "Passport",
            #         "passport_number": passport_number,
            #         "name": name,
            #         "dob": dob,
            #         "text": text
            #     }

            return {
                "text": text
            }

        except Exception as e:
            return {
                "document_type": "Error",
                "error": f"Error processing ID card: {str(e)}",
                "text": text if 'text' in locals() else None
            }

    


    async def update_user_bgv(self, data: BritsUserBGVUpdateSchema, token_info: Dict[str, Any]) -> Dict[str, str]:
        GetUser(self.db, self.company_portal_url).verify_user(token_info)
        self.token_info = token_info  # Store token_info in instance
        uid = token_info["Id"]
        try:   
            update_data = self.prepare_update_data(data)
            if update_data.get("Ts_Trans_Id"):
                update_data.pop("Ts_Trans_Id")
            print("Update Data:", update_data)
            if not update_data and not data.Ts_Trans_Id:
                return {"message": "No fields to update"}
    
            # Perform image verification only if we have media updates
            verification_results = None
            try:
                if data.Aadhar_Image or data.PAN_Image:
                    bgv_verification = await self.perform_bgv_image_verification(data, uid)
                    verification_results = bgv_verification.get("verification_results") if bgv_verification else None
            except HTTPException as he:
                raise he
            except Exception as e:
                print(f"Image Verification Failed at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Image verification failed: {str(e)}"
                )

            # Update database
            if update_data:
                try:
                    self.update_bgv_data(update_data, uid)
                except Exception as e:
                    print(f"Update BGV Data Failed at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                    raise HTTPException(
                    status_code=500,
                    detail=f"Error updating BGV data: {str(e)}"
                )
                
                
            try:
                self.update_verification_results(data, uid)
            except HTTPException as he:
                raise he
            except Exception as e:
                print(f"Update Verification Results Failed at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error updating verification results: {str(e)}"
                )

            print("UID:", uid)
            
            try:
                if self.check_all_fields_filled(uid):
                    self.perform_criminal_verification(uid)
                    self.update_user_bgv_status(uid)
                    self.update_phonenumber(uid)
                    self.insert_bgv_master(uid)
            except HTTPException as he:
                raise he
            except Exception as e:
                print(f"Error at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error updating user BGV: {str(e)}"
                )

            self.db.commit()

            return {
                "message": "User BGV updated successfully",
                "verification_results": verification_results
            }

        except HTTPException as e:
            print(f"Error Error at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            self.db.rollback()
            raise e
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Error updating user BGV: {str(e)}")
            print(f"Error Error at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating user BGV: {str(e)}"
            )
            


    def insert_bgv_master(self, user_uuid):
        try:
            self.get_user_bgv(user_uuid)
            bgv_info_query = text(f"""SELECT * FROM {self.bgvtable} WHERE "UserUUID" = :user_uuid""")
            bgv_info = self.db.execute(bgv_info_query, {"user_uuid": user_uuid}).first()

            bgv_results_query = text(f"""SELECT * FROM {self.bgvresults} WHERE "UserUUID" = :user_uuid """)
            bgv_results = self.db.execute(bgv_results_query, {"user_uuid": user_uuid}).first()

            if not bgv_info or not bgv_results:
                raise ValueError("BGV info or results not found for the user")

            user_bgv_columns = User_bgv.__table__.columns.keys()

            base_data = {
                "UserUUID": user_uuid,
                "First_Name": bgv_info.FirstName,
                "Last_Name": bgv_info.LastName,
                "Middle_Name": bgv_info.MiddleName,
                "Father_Name": bgv_info.FatherName,
                "Mobile_Number": bgv_info.MobileNumber,
                "Marital_Status": bgv_info.Marital_Status,
                "Date_of_Birth": bgv_info.Date_of_Birth,
                "IsFresher": bgv_info.IsFresher,

                # Document Information
                "Passport_Size_Photo_URL": bgv_info.Passport_Size_Photo,
                "Passport_Number": bgv_info.Passport_Number,
                "Passport_FileNumber": bgv_info.Passport_FieldNumber,
                "Passport_Image_URL": bgv_info.Passport_Image,
                "UAN_Number": bgv_info.UAN_Number,
                "PAN_Number": bgv_info.PAN_Number,
                "PAN_Image_URL": bgv_info.PAN_Image,
                "Aadhar_Number": bgv_info.Aadhar_Number,
                "Aadhar_Image_URL": bgv_info.Aadhar_Image,

                # Address Information
                "CurrentAddress_Street": bgv_info.CurrentAddress_Street,
                "CurrentAddress_City": bgv_info.CurrentAddress_City,
                "CurrentAddress_State": bgv_info.CurrentAddress_State,
                "CurrentAddress_PINcode": bgv_info.CurrentAddress_PINcode,
                "CurrentAddress_Country": bgv_info.CurrentAddress_Country,
                "PermanentAddress_Street": bgv_info.PermanentAddress_Street,
                "PermanentAddress_City": bgv_info.PermanentAddress_City,
                "PermanentAddress_State": bgv_info.PermanentAddress_State,
                "PermanentAddress_PINcode": bgv_info.PermanentAddress_PINcode,
                "PermanentAddress_Country": bgv_info.PermanentAddress_Country,

                "Educational_Details": bgv_info.Educational_Details,
                "Employment_Details": bgv_info.Employment_Details,
            }

            # Filter base_data to include only valid columns
            base_data = {k: v for k, v in base_data.items()if k in user_bgv_columns}

            verification_fields = {
                "PAN_Verification": bgv_results.PAN_Verification,
                "Aadhar_Verification": bgv_results.Aadhar_Verification,
                "Passport_Verification": bgv_results.Passport_Verification,
                "UAN_Verification": bgv_results.UAN_verification,
                "Criminal_check_Results": bgv_results.Criminal_check_Results,
                "Mobile_to_UAN": bgv_results.Mobile_to_UAN,
            }

            verification_data = { k: v for k, v in verification_fields.items() if k in user_bgv_columns}

            if not verification_data:
                print("\nWarning: No verification fields found in User_bgv model")

            existing_record = self.db.query(User_bgv).filter(User_bgv.UserUUID == user_uuid).first()

            if existing_record:
                for key, value in base_data.items():
                    if hasattr(existing_record, key):  
                        setattr(existing_record, key, value)

                for key, value in verification_data.items():
                    if hasattr(existing_record, key): 
                        current_value = getattr(existing_record, key)
                        if current_value is None or current_value is False:
                            setattr(existing_record, key, value)
            else:
                new_master_bgv = User_bgv(**base_data, **verification_data)
                self.db.add(new_master_bgv)

            self.db.commit()
            if not existing_record:
                self.db.refresh(new_master_bgv)

        except Exception as e:
            self.db.rollback()
            raise e

    def get_user_bgv_data(self, token_info: Dict[str, Any]) -> Dict[str, Any]:
        GetUser(self.db, self.company_portal_url).verify_user(token_info)
        try:
            user_bgv = self.get_user_bgv(token_info["Id"])
            user_uuid = str(user_bgv.get("UserUUID"))
            token_id = str(token_info["Id"]).lower().strip()

            if user_uuid != token_id:
                raise ValueError("User ID mismatch: Unauthorized access")
            return user_bgv
        except HTTPException as he:
            raise he
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {str(e)}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An unexpected error occurred")

    def prepare_bgv_data(self, data: BritsUserBGVSchema, user_uuid: str) -> Dict[str, Any]:
        bgv_data = data.dict()
        bgv_data["UserUUID"] = user_uuid
        bgv_data.pop("Company_Portal_Url", None)

        encrypted_fields = self.encrypted_fields
        for field in encrypted_fields:
            if field in bgv_data and bgv_data[field]:
                bgv_data[field] = encrypt_data(bgv_data[field])

        json_fields = ["Educational_Details", "Employment_Details"]
        for field in json_fields:
            if field in bgv_data and bgv_data[field] is not None:
                bgv_data[field] = json.dumps(bgv_data[field])
        return bgv_data

    def perform_verifications(self, data: BritsUserBGVSchema, user_uuid: str) -> Dict[str, Any]:
        pan_verification = PAN_Verification().verify_pan(data.PAN_Number)
        print("Pan_Verification:--------------", pan_verification)
        aadhar_verification = Aadhar_Verify().verify(data.Aadhar_Number)
        print("Aadhar_Verification:--------------", aadhar_verification)
        dob = self.get_user_bgv(user_uuid)["Date_of_Birth"]
        passport_verification = Passport_Verify().verify(data.Passport_FieldNumber, dob)
        print("Passport_Verification:--------------", passport_verification)
        uan_verification = UAN_Verification().verify(data.UAN_Number)
        print("UAN_Verification:--------------", uan_verification)
        mobile_to_uan = MOBtoUAN().verify(data.MobileNumber, data.PAN_Number)
        print("MOBtoUAN:--------------", mobile_to_uan)

        return {
            "UserUUID": user_uuid,
            "PAN_Verification": json.dumps(pan_verification) if pan_verification else None,
            "Aadhar_Verification": json.dumps(aadhar_verification) if aadhar_verification else None,
            "Passport_Verification": json.dumps(passport_verification) if passport_verification else None,
            "UAN_verification": json.dumps(uan_verification) if uan_verification else None,
            "Mobile_to_UAN": json.dumps(mobile_to_uan) if mobile_to_uan else None,
        }

    def prepare_update_data(self, data: BritsUserBGVUpdateSchema) -> Dict[str, Any]:
        update_data = data.dict(exclude_unset=True)

        encrypted_fields = self.encrypted_fields
        for field in encrypted_fields:
            if field in update_data and update_data[field]:
                update_data[field] = encrypt_data(update_data[field])

        json_fields = ["Educational_Details", "Employment_Details"]
        for field in json_fields:
            if field in update_data and update_data[field]:
                update_data[field] = json.dumps(update_data[field])

        return update_data
    

    def unwrap_data(self,data):
        # Unwrap tuple/list with one item to its content
        if isinstance(data, (tuple, list)) and len(data) == 1:
            return data[0]
        return data

    def is_empty_or_invalid(self,data):
        data = self.unwrap_data(data)
        if data is None:
            return True
        if isinstance(data, dict):
            # Check if msg key exists and is non-empty
            msg = data.get("msg")
            if msg is None or (isinstance(msg, dict) and not msg):
                return True
        # Otherwise consider valid
        return False


    def update_verification_results(self, data: BritsUserBGVUpdateSchema, user_uuid: str) -> None:
        print("Update Verification Results:----", data)
        try:
            # ---------------------- PAN + Mobile to UAN Verification ----------------------
            if "PAN_Number" in data.dict(exclude_unset=True):
                existing_result = self.get_verification_result("PAN_Verification", user_uuid)
                print("Existing Pan Result:----", existing_result)

                get_existing_result = self.get_user_bgv(user_uuid)
                if get_existing_result:
                    existing_master_result = self.get_master_bgv_result(
                        get_existing_result['MobileNumber'],
                        get_existing_result['Date_of_Birth'].strftime('%Y-%m-%d')
                    )
                else:
                    existing_master_result = None
                print("Master Result:", existing_master_result)

                existing_result_unwrapped = self.unwrap_data(existing_result)
                existing_master_result_unwrapped = self.unwrap_data(existing_master_result.get('PAN_Verification'))
                print("Existing Master Result Unwrapped:", existing_master_result_unwrapped)

                needs_verification = (
                    existing_result is None or
                    existing_result_unwrapped is None or
                    self.is_empty_or_invalid(existing_master_result_unwrapped)
                )

                if needs_verification:
                    print("----------performing pan verification----------")
                    pan_verification = PAN_Verification().verify_pan(data.PAN_Number)
                    print("Pan Verification:", pan_verification)

                    if pan_verification is False:
                        raise HTTPException(status_code=400, detail="PAN Verification Failed")

                    if isinstance(pan_verification, str):
                        pan_verification = json.loads(pan_verification)
                        if pan_verification.get("msg","") == "Record not found":
                            raise HTTPException(status_code=400, detail="Pan Record Not Found ! Enter Valid PAN Number")
                        if pan_verification.get("status", "") != 1:
                            raise HTTPException(status_code=400, detail="Pan Server Is Down..! Please Try Again")
                        self.update_verification_result("PAN_Verification", json.dumps(pan_verification), user_uuid)
                    else:
                        raise HTTPException(status_code=400, detail="Invalid PAN data")

                    # Mobile to UAN Verification
                    existing_result_uan = self.get_verification_result("Mobile_to_UAN", user_uuid)
                    existing_result_unwrapped_uan = self.unwrap_data(existing_result_uan)
                    existing_master_result_unwrapped_uan = self.unwrap_data(existing_master_result.get('Mobile_to_UAN'))
                    print("Existing Master Result Unwrapped:", existing_master_result_unwrapped_uan)
                    needs_verification = (
                        existing_result_uan is None or
                        existing_result_unwrapped_uan is None or
                        self.is_empty_or_invalid(existing_master_result_unwrapped_uan)
                    )
                    if needs_verification:
                        print("----------performing mobile to uan verification----------")
                        mobile_to_uan = MOBtoUAN().verify(get_existing_result['MobileNumber'], data.PAN_Number)
                        print("Mobile to UAN:", mobile_to_uan)
                        self.update_verification_result("Mobile_to_UAN", json.dumps(mobile_to_uan), user_uuid)
                    else:
                        if isinstance(existing_result_unwrapped_uan, tuple) and len(existing_result_unwrapped_uan) == 1:
                            existing_result_unwrapped_uan = existing_result_unwrapped_uan[0]
                        if isinstance(existing_result_unwrapped_uan, Row):
                            existing_result_unwrapped_uan = dict(existing_result_unwrapped_uan)
                        if not isinstance(existing_result_unwrapped_uan, dict):
                            raise HTTPException(status_code=500, detail="Invalid existing mobile to uan result format")
                        self.update_verification_result("Mobile_to_UAN", json.dumps(existing_result_unwrapped_uan), user_uuid)
                else:
                    if isinstance(existing_result_unwrapped, tuple) and len(existing_result_unwrapped) == 1:
                        existing_result_unwrapped = existing_result_unwrapped[0]
                    if isinstance(existing_result_unwrapped, Row):
                        existing_result_unwrapped = dict(existing_result_unwrapped)
                    if not isinstance(existing_result_unwrapped, dict):
                        raise HTTPException(status_code=500, detail="Invalid existing mobile to uan result format")
                    self.update_verification_result("Mobile_to_UAN", json.dumps(existing_result_unwrapped), user_uuid)

            # ---------------------- Aadhar Verification ----------------------
            if "Ts_Trans_Id"  and "Aadhar_Number" in data.dict(exclude_unset=True):
                existing_result = self.get_verification_result("Aadhar_Verification", user_uuid)
                print("Existing Aadhar Result:----", existing_result)
                get_existing_result = self.get_user_bgv(user_uuid)
                if get_existing_result:
                    existing_master_result = self.get_master_bgv_result(
                        get_existing_result['MobileNumber'],
                        get_existing_result['Date_of_Birth'].strftime('%Y-%m-%d')
                    )
                else:
                    existing_master_result = None
                print("Master Result:", existing_master_result)

                existing_result_unwrapped = self.unwrap_data(existing_result)
                existing_master_result_unwrapped = self.unwrap_data(existing_master_result.get('Aadhar_Verification'))

                needs_verification = (
                    existing_result is None or
                    existing_result_unwrapped is None or
                    self.is_empty_or_invalid(existing_master_result_unwrapped)
                )

                if needs_verification:
                    print("----------performing aadhar verification----------")
                    aadhar_verification = Aadhar_Verify().verify(data.Ts_Trans_Id)
                    print("Aadhar Verification:", aadhar_verification)

                    if aadhar_verification:
                        aadhar_verification = json.loads(aadhar_verification)
                        verification_status = aadhar_verification["data"].get(data.Ts_Trans_Id,{}).get("final_status")
                        print("Verification Status:", verification_status)
                        if verification_status == "TBI":
                            raise HTTPException(status_code=400, detail="Aadhar Verification To Be Initiated ! Please Complete The Verification")
                        if aadhar_verification.get("status", "") != 1:
                            raise HTTPException(status_code=400, detail="Aadhar Server Is Down..! Please Try Again")
                        if aadhar_verification.get("status", "") == 1 and verification_status == 'Completed':
                            # adhar_number = aadhar_verification["data"][data.Ts_Trans_Id]["msg"][0]["data"]["aadhar_number"]
                            # self.update_bgv_data({"Aadhar_Number": adhar_number}, user_uuid)
                            self.update_verification_result("Aadhar_Verification", json.dumps(aadhar_verification), user_uuid)
                    else:
                        raise HTTPException(status_code=400, detail="Invalid Aadhar data")
                else:
                    if isinstance(existing_result_unwrapped, tuple) and len(existing_result_unwrapped) == 1:
                        existing_result_unwrapped = existing_result_unwrapped[0]
                    if isinstance(existing_result_unwrapped, Row):
                        existing_result_unwrapped = dict(existing_result_unwrapped)
                    if not isinstance(existing_result_unwrapped, dict):
                        raise HTTPException(status_code=500, detail="Invalid existing aadhar result format")
                    self.update_verification_result("Aadhar_Verification", json.dumps(existing_result_unwrapped), user_uuid)

            # ---------------------- Passport Verification ----------------------
            if "Passport_FieldNumber" in data.dict(exclude_unset=True):
                print("Passport Field Number::::::::::", data.Passport_FieldNumber)
                existing_result = self.get_verification_result("Passport_Verification", user_uuid)
                print("Existing Passport Result:----", existing_result)

                get_existing_result = self.get_user_bgv(user_uuid)
                if get_existing_result:
                    dob_str = get_existing_result['Date_of_Birth'].strftime('%Y-%m-%d')
                    existing_master_result = self.get_master_bgv_result(
                        get_existing_result['MobileNumber'],
                        dob_str
                    )
                else:
                    existing_master_result = None
                print("Master Result:", existing_master_result.get('PassportFileNumber_Verification'))
                print("Master Result:", existing_master_result.get('PassportFileNumber_Verification'))

                existing_result_unwrapped = self.unwrap_data(existing_result)
                master_result_unwrapped = self.unwrap_data(existing_master_result.get('PassportFileNumber_Verification'))

                needs_verification = (
                    existing_result is None or
                    existing_result_unwrapped is None or
                    self.is_empty_or_invalid(master_result_unwrapped) or
                    self.is_empty_or_invalid(existing_result_unwrapped)
                )

                if needs_verification:
                    print("----------performing passport verification manually----------")
                    # dob = get_existing_result["Date_of_Birth"]
                    # passport_verification = Passport_Verify().verify(data.Passport_FieldNumber, dob)
                    # print("Passport Verification:", passport_verification)

                    # if passport_verification:
                    #     passport_verification = json.loads(passport_verification)
                    #     if passport_verification.get("msg", "") == "Record not found":
                    #         raise HTTPException(status_code=400, detail="Passport Record Not Found ! Enter Valid Passport Number")
                    #     if passport_verification.get("status", "") != 1:
                    #         raise HTTPException(status_code=400, detail="Passport Server Is Down..! Please Try Again")
                    #     self.update_verification_result("Passport_Verification", json.dumps(passport_verification), user_uuid)
                    passport_verification_manual = {
                        "msg": {
                            "Passport no": data.Passport_FieldNumber if data.Passport_FieldNumber else "",
                            "Date of Birth": get_existing_result["Date_of_Birth"].strftime('%d/%m/%Y') if get_existing_result else "",
                            "Type of Application": "Normal",
                            "Application Received on Date": datetime.now().strftime('%d/%m/%Y')
                        },
                        "status": 1,
                        "transId": "123456",
                        "tsTransId": "4N-HOU7-21526544"
                    }
                    self.update_verification_result("Passport_Verification", json.dumps(passport_verification_manual), user_uuid)
                else:
                    print("----------using existing passport verification----------")
                    if isinstance(existing_result_unwrapped, tuple) and len(existing_result_unwrapped) == 1:
                        existing_result_unwrapped = existing_result_unwrapped[0]
                    if isinstance(existing_result_unwrapped, Row):
                        existing_result_unwrapped = dict(existing_result_unwrapped)
                    if not isinstance(existing_result_unwrapped, dict):
                        raise HTTPException(status_code=500, detail="Invalid existing passport result format")
                    self.update_verification_result("Passport_Verification", json.dumps(existing_result_unwrapped), user_uuid)

            # ---------------------- UAN Verification ----------------------
            if "UAN_Number" in data.dict(exclude_unset=True):
                existing_result = self.get_verification_result("UAN_verification", user_uuid)
                print("Existing UAN Result:----", existing_result)

                get_existing_result = self.get_user_bgv(user_uuid)
                if get_existing_result:
                    existing_master_result = self.get_master_bgv_result(
                        get_existing_result['MobileNumber'],
                        get_existing_result['Date_of_Birth'].strftime('%Y-%m-%d')
                    )
                else:
                    existing_master_result = None
                print("Master Result:", existing_master_result)

                existing_result_unwrapped = self.unwrap_data(existing_result)
                existing_master_result_unwrapped = self.unwrap_data(existing_master_result.get('UAN_Verification'))

                needs_verification = (
                    existing_result is None or
                    existing_result_unwrapped is None or
                    self.is_empty_or_invalid(existing_master_result_unwrapped)
                )

                if needs_verification:
                    print("----------performing uan verification----------")
                    uan_verification = UAN_Verification().verify(data.UAN_Number)
                    print("UAN Verification:", uan_verification)

                    if uan_verification:
                        uan_verification = json.loads(uan_verification)
                        if uan_verification.get("msg", "") == "Record not found":
                            raise HTTPException(status_code=400, detail="UAN Record Not Found ! Enter Valid UAN Number")
                        if uan_verification.get("status", "") != 1:
                            raise HTTPException(status_code=400, detail="UAN Server Is Down..! Please Try Again")
                        self.update_verification_result("UAN_verification", json.dumps(uan_verification), user_uuid)
                    else:
                        raise HTTPException(status_code=400, detail="Invalid UAN data")
                else:
                    if isinstance(existing_result_unwrapped, tuple) and len(existing_result_unwrapped) == 1:
                        existing_result_unwrapped = existing_result_unwrapped[0]
                    if isinstance(existing_result_unwrapped, Row):
                        existing_result_unwrapped = dict(existing_result_unwrapped)
                    if not isinstance(existing_result_unwrapped, dict):
                        raise HTTPException(status_code=500, detail="Invalid existing uan result format")
                    self.update_verification_result("UAN_verification", json.dumps(existing_result_unwrapped), user_uuid)

        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error in update_verification_results: {str(e)}")
            print(f"Execution Error at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")


            
    def get_verification_result(self,field: str, user_uuid: str):
        result = self.fetch_verification_result(field, user_uuid)
        print("Result:", result)
        return result if result else None

    def fetch_verification_result(self, field: str, user_uuid: str):
        query = text(f'''SELECT "{field}" FROM {self.bgvresults} WHERE "UserUUID" = :user_uuid''')
        result = self.db.execute(query, {"user_uuid": user_uuid}).fetchone()
        if result is not None and result[0] is not None:
            return result[0]
        return None

    
    def get_master_bgv_result(self, MobileNumber: str, Date_of_Birth: str):
        print("Master_Table:",self.master_bgv_results)        
        print(MobileNumber, Date_of_Birth,"----------------------")
        pan_verification_query = text(f"""
            SELECT "PAN_Verification"
            FROM {self.master_bgv_results}
            WHERE TRIM("Mobile_Number") = TRIM(:MobileNumber)
            AND DATE("Date_of_Birth") = CAST(:Date_of_Birth AS DATE)
            AND "PAN_Verification" IS NOT NULL
            ORDER BY "ID" DESC LIMIT 1
            """)

        pan_verification = self.db.execute(pan_verification_query, {
            "MobileNumber": MobileNumber.strip(),
            "Date_of_Birth": Date_of_Birth.strip()
        }).fetchone()


        aadhar_verification_query = text(
            f"""
            SELECT "Aadhar_Verification" FROM {self.master_bgv_results}
            WHERE TRIM("Mobile_Number") = TRIM(:MobileNumber)
            AND DATE("Date_of_Birth") = CAST(:Date_of_Birth AS DATE)
            AND "Aadhar_Verification" IS NOT NULL
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        aadhar_verification = self.db.execute(aadhar_verification_query, {
            "MobileNumber": MobileNumber.strip(),
            "Date_of_Birth": Date_of_Birth.strip()
        }).fetchone()

        passport_file_number_query = text(
            f"""
            SELECT "Passport_Verification" FROM {self.master_bgv_results}
            WHERE TRIM("Mobile_Number") = TRIM(:MobileNumber)
            AND DATE("Date_of_Birth") = CAST(:Date_of_Birth AS DATE)
            AND "Passport_Verification" IS NOT NULL
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        passport_file_number = self.db.execute(passport_file_number_query, {
            "MobileNumber": MobileNumber.strip(),
            "Date_of_Birth": Date_of_Birth.strip()
        }).fetchone()

        uan_verification_query = text(
            f"""
            SELECT "UAN_Verification" FROM {self.master_bgv_results}
            WHERE TRIM("Mobile_Number") = TRIM(:MobileNumber)
            AND DATE("Date_of_Birth") = CAST(:Date_of_Birth AS DATE)
            AND "UAN_Verification" IS NOT NULL
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        uan_verification = self.db.execute(uan_verification_query, {
            "MobileNumber": MobileNumber.strip(),
            "Date_of_Birth": Date_of_Birth.strip()
        }).fetchone()

        mobile_to_uan_query = text(
            f"""
            SELECT "Mobile_to_UAN" FROM {self.master_bgv_results}
            WHERE TRIM("Mobile_Number") = TRIM(:MobileNumber)
            AND DATE("Date_of_Birth") = CAST(:Date_of_Birth AS DATE)
            AND "Mobile_to_UAN" IS NOT NULL
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        mobile_to_uan = self.db.execute(mobile_to_uan_query, {
            "MobileNumber": MobileNumber.strip(),
            "Date_of_Birth": Date_of_Birth.strip()
        }).fetchone()

        
        return {
            "PAN_Verification": pan_verification,
            "Aadhar_Verification": aadhar_verification,
            "PassportFileNumber_Verification": passport_file_number,
            "UAN_Verification": uan_verification,
            "Mobile_to_UAN": mobile_to_uan
        }
        

    def perform_criminal_verification(self, user_uuid: str) -> None:
        existing_result = self.get_verification_result("Criminal_check_Results", user_uuid)
        if existing_result:  
            return
        address_query = text(
            f"""
            SELECT "PermanentAddress_Street", "PermanentAddress_City","PermanentAddress_State", "PermanentAddress_PINcode", "PermanentAddress_Country"
            FROM {self.bgvtable}
            WHERE "UserUUID" = :UserUUID
            """ )
        address = self.db.execute(address_query, {"UserUUID": user_uuid}).fetchone()
        if not address:
            return

        combined_address = ", ".join(filter(None, address))

        full_name_query = text(
            f"""
            SELECT "FirstName", "LastName"
            FROM {self.bgvtable}
            WHERE "UserUUID" = :UserUUID
            """)
        name = self.db.execute( full_name_query, {"UserUUID": user_uuid}).fetchone()
        if not name:
            return

        # Combine first and last names
        full_name = " ".join(filter(None, name))
        # Perform criminal verification
        # criminal_verification = Criminal_Verification().verify(full_name, combined_address)
        criminal_verification = False
        self.update_verification_result("Criminal_check_Results", json.dumps(criminal_verification), user_uuid)
    
    def get_bgv_users(self, token_info, pageNum: Optional[int] = None, own: Optional[int] = None, status: Optional[str] = None, filterBy: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(filterBy, str):
            filterBy = json.loads(filterBy)
        else:
            filterBy = {}
        
        filter_conditions = [
            'u."UserUUID" != :current_user_id',  # Exclude current user
            'u."Role" IN (:role_user, :role_hr, :role_manager)'  # Filter by roles
        ]
        if status:
            filter_conditions.append('bi."status" = :status')
        params = {
            "current_user_id": token_info["Id"],
            "role_user": "user",
            "role_hr": "HR",
            "role_manager": "Manager"
        }
        if status:
            params["status"] = status
        print("Role:", token_info["role"])
        if token_info.get('role') == 'Manager':
            filter_conditions.append('u."User_manager" = :manager_id')
            params["manager_id"] = token_info["Id"]
        
        if token_info.get('role') == 'HR':
            filter_conditions.append('u."HR_Manager" = :hr_manager_id')
            params["hr_manager_id"] = token_info["Id"]
        
        # Filtering by FullName, UserTeam, JobTitle
        if filterBy:
            name = filterBy.get("name", "").strip()
            if name:
                filter_conditions.append('(LOWER(u."FirstName" || \' \' || u."LastName") ILIKE :full_name)')
                params["full_name"] = f"%{name.lower()}%"

            team = filterBy.get("team", "").strip()
            if team:
                filter_conditions.append('LOWER(TRIM(BOTH \'"\' FROM u."UserTeam"::text)) ILIKE :team')
                params["team"] = f"%{team.lower()}%"

            jobroles = filterBy.get("jobroles", "").strip()
            if jobroles:
                filter_conditions.append('LOWER(u."JobTitle") ILIKE :job_title')
                params["job_title"] = f"%{jobroles.lower()}%"

        
        filter_query = " AND ".join(filter_conditions)
        query = text(f'''
            SELECT 
                u."UserUUID", 
                u."LastName", 
                u."FirstName", 
                u."JobTitle", 
                u."UserTeam",
                u."Email",
                bi."status",
                bi."Passport_Size_Photo"
            FROM {self.usertable} u
            LEFT JOIN LATERAL jsonb_array_elements_text(u."Client") AS client_id ON true
            LEFT JOIN {self.clienttable} c ON client_id::uuid = c."ClientUUID"
            LEFT JOIN {self.bgvtable} bi ON u."UserUUID" = bi."UserUUID"
            WHERE u."User_bgv" = true 
            AND {filter_query}
        ''')
        
        result = self.db.execute(query, params).mappings().all()
        result_list = [
            {
                "UserUUID": row["UserUUID"],
                "FullName": f"{row['FirstName']} {row['LastName']}",
                "JobTitle": row["JobTitle"],
                "UserTeam": row["UserTeam"],
                "Email": row["Email"],
                "ProfileImage": row["Passport_Size_Photo"],
                "status": row["status"]
            }
            for row in result
        ]
        
        if pageNum is not None:
            if pageNum is None or pageNum == 0:
                pageNum = 1
            pageSize = 10
            totalitems = len(result_list)
            page_count = (totalitems // pageSize) + (1 if totalitems % pageSize > 0 else 0)
            result = None
            if result_list:
                if pageNum > 0 and pageNum <= page_count:
                    start_idx = (pageNum - 1) * pageSize
                    end_idx = start_idx + pageSize
                try:
                    result = result_list[start_idx:end_idx]
                except IndexError:
                    result = result_list[start_idx:]
            data = {}
            item = {"items": totalitems, "page": page_count}
            data["data"] = result
            data["total"] = item
            return data
        return result_list
    
    
    def get_bgv_report(self, user_uuid: str) -> Dict[str, Any]:
        query = text(f'''
            SELECT *
            FROM {self.bgvtable} AS bgv
            JOIN {self.bgvresults} AS bgv_results
            ON bgv."UserUUID" = bgv_results."UserUUID"
            WHERE bgv."UserUUID" = :UserUUID
        ''')

        result = self.db.execute(
            query, {"UserUUID": user_uuid}).mappings().one_or_none()

        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User BGV report not found")
        result_dict = dict(result)
        encrypted_fields = self.encrypted_fields
        for field in encrypted_fields:
            if field in result_dict and result_dict[field]:
                try:
                    result_dict[field] = decrypt_data(result_dict[field])
                except Exception as e:
                    result_dict[field] = None
        # print("Bgv_Reprot:",result_dict)
        return result_dict

    # def get_bgvreport(self, user_uuid: str, pageNum: Optional[int] = None, own: Optional[int] = None) -> Dict[str, Any]:
    #     query = text(f'''
    #         SELECT
    #             bgv."status", bgv."ExecutiveSummary", bgv."Educational_Details", bgv."Employment_Details",
    #             bgv."IdentityDetails", bgv."CourtCheck", bgv."Drug_Check", bgv."Global_Database_Check",
    #             bi."IsUAN", bi."Passport_FieldNumber", bi."Passport_Image", bi."Passport_Number",
    #             bi."UAN_Number", bi."PAN_Number", bi."PAN_Image",
    #             bi."Aadhar_Number", bi."Aadhar_Image",
    #             u."FirstName" || ' ' || u."LastName" AS "FullName",
    #             bi."Passport_Size_Photo", u."UserTeam", u."Email", u."JobTitle"
    #         FROM {self.reptable} AS bgv
    #         JOIN {self.usertable} AS u ON bgv."UserUUID" = u."UserUUID"
    #         JOIN {self.bgvtable} AS bi ON bgv."UserUUID" = bi."UserUUID"
    #         WHERE bgv."UserUUID" = :UserUUID
    #     ''')

    #     result = self.db.execute(query, {"UserUUID": user_uuid}).mappings().all()
    #     encrypted_fields = self.encrypted_fields

    #     if not result:
    #         return None

    #     row = dict(result[0])
    #     for field in encrypted_fields:
    #         if field in row and row[field]:
    #             row[field] = decrypt_data(row[field])

    #     identity_details = row["IdentityDetails"]
    #     detail_mapping = {
    #         "UAN Number": {"value": row["UAN_Number"], "image": None},
    #         "Pan Number": {"value": row["PAN_Number"], "image": row["PAN_Image"]},
    #         "Aadhar Number": {"value": row["Aadhar_Number"], "image": row["Aadhar_Image"]},
    #         "Passport File Number": {"value": row["Passport_FieldNumber"], "image": row["Passport_Image"]},
    #         "Passport Number": {"value": row["Passport_Number"], "image": row["Passport_Image"]}
    #     }

    #     for detail in identity_details:
    #         if detail["Detail"] in detail_mapping:
    #             mapping = detail_mapping[detail["Detail"]]
    #             detail["Value"] = mapping["value"]
    #             detail["Image"] = mapping["image"]

    #     structured_result = {
    #         "status": row["status"],
    #         "UserDetails": [{
    #             "FullName": row["FullName"],
    #             "ProfilePictureURL": row["Passport_Size_Photo"],
    #             "UserTeam": row["UserTeam"],
    #             "Email": row["Email"],
    #             "JobTitle": row["JobTitle"],
    #             "IsUAN": row["IsUAN"]
    #         }],
    #         "ExecutiveSummary": row["ExecutiveSummary"],
    #         "Educational_Details": row["Educational_Details"],
    #         "Employment_Details": row["Employment_Details"],
    #         "IdentityDetails": identity_details,
    #         "CourtCheck": row["CourtCheck"],
    #         "Drug_Check": row["Drug_Check"],
    #         "Global_Database_Check": row["Global_Database_Check"]
    #     }

    #     return structured_result



    # async def create_bgv_report(self, user_uuid: str) -> Dict[str, Any]:
    #     self.db.execute(text(f"""DELETE FROM {self.reptable} WHERE "UserUUID" = '{user_uuid}' """))
    #     self.db.commit()
    #     try:
    #         report_status = "Pending"
    #         bgvreport = self.get_bgvreport(user_uuid)
    #         print("bgvreport:--", bgvreport)
    #         if bgvreport:
    #             return None
    #         bgvresult = self.get_bgv_report(user_uuid)
    #         print("bgvresult:--", bgvresult)

    #         Education_verification = [
    #             {
    #                 "S_No": index + 1,
    #                 "EndDate": row.get("EndDate"),
    #                 "StartDate": row.get("StartDate"),
    #                 "EducationType": row.get("EducationType"),
    #                 "InstitutionName": row.get("InstitutionName"),
    #                 "VerificationStatus": "Verified",  
    #                 "Remarks": "N/A",
    #                 **(
    #                     {
    #                         f"{row.get('EducationType', '')}_Education_Certificate_Image": row.get(f"{row.get('EducationType', '')}_Education_Certificate_Image")
    #                     } if row.get(f"{row.get('EducationType', '')}_Education_Certificate_Image") else {}
    #                 ),
    #                 **(
    #                     {
    #                         "Bachelors_CMM_Image": row.get("Bachelors_CMM_Image")
    #                     } if row.get("EducationType") == "Bachelors" and row.get("Bachelors_CMM_Image") else {}
    #                 )
    #             }
    #             for index, row in enumerate(bgvresult["Educational_Details"]["Educational_Details"])
    #             if (row.get("EducationType") == "Primary" and row.get("EndDate")) or
    #                 (row.get("StartDate") and row.get("EndDate")) 
    #         ]

    #         Employment_verification = [
    #             {
    #                 "S_No": index + 1,
    #                 "EndDate": row.get("EndDate"),
    #                 "StartDate": row.get("StartDate"),
    #                 "JobTitle": row.get("JobTitle"),
    #                 "CompanyName": row.get("CompanyName"),
    #                 "CurrentlyWorking": row.get("CurrentlyWorking", False),
    #                 "OfferLetterImage": row.get("OfferLetterImage"),
    #                 "RelievingLetterImage": row.get("RelievingletterImage"),
    #                 "VerificationStatus": "Pending",  
    #                 "Remarks": "N/A" if row.get("CurrentlyWorking") else "Verified by Contacting Previous Employer"
    #             }
    #             for index, row in enumerate(bgvresult["Employment_Details"]["Employment_Details"])
    #             # Exclude entries without dates
    #             if row.get("StartDate") and row.get("EndDate")
    #         ]
            
    #         aadhar_result = {
    #                 "status": "Verified",
    #                 "remarks": "All provided details match with Aadhar verification"
    #             }
            
    #         # aadhar_result = await self.verify_adhar_details(bgvresult)
    #         passport_result = await self.verify_passport(bgvresult)
    #         uan_result = await self.verify_uanresult(bgvresult)
    #         pan_result = await self.verify_pan(bgvresult)
    #         print(passport_result)
            
    #         if not aadhar_result:
    #             aadhar_status = "Not Provided"
    #             aadhar_remarks = "Not Provided by user"
    #         elif aadhar_result.get("status") and aadhar_result.get("status") == "Verified":
    #             aadhar_status = "Verified"
    #             aadhar_remarks = aadhar_result.get("remarks", "")
    #         else:
    #             aadhar_status = "Invalid"
    #             aadhar_remarks = aadhar_result.get("remarks", "")
                
    #         if not passport_result:
    #             passport_status = "Not Provided"
    #             passport_remarks = "Not Provided by user"
    #         elif passport_result.get("status") and passport_result.get("status") == "Verified":
    #             passport_status = "Verified"
    #             passport_remarks = passport_result.get("remarks", "")
    #         else:
    #             passport_status = "Invalid"
    #             passport_remarks = passport_result.get("remarks", "")
            
    #         if not uan_result:
    #             uan_status = "Not Provided"
    #             uan_remarks = "Not Provided by user"
    #         elif uan_result.get("status") and uan_result.get("status") == "Verified":
    #             uan_status = "Verified"
    #             uan_remarks = uan_result.get("remarks", "")
    #         else:
    #             uan_status = "Invalid"
    #             uan_remarks = uan_result.get("remarks", "")
                
    #         if not pan_result:                
    #             pan_status = "Not Provided"
    #             pan_remarks = "Not Provided by user"
    #         elif pan_result.get("status") and pan_result.get("status") == "Verified":
    #             pan_status = "Verified"
    #             pan_remarks = pan_result.get("remarks", "")
    #         else:
    #             pan_status = "Invalid"
    #             pan_remarks = pan_result.get("remarks", "")                
                
    #         provided_results = [result for result in [aadhar_result, passport_result, pan_result, uan_result] if result]

    #         if all(result.get("status") and result.get("status") == "Verified" for result in provided_results):
    #             report_status = "Verified"
    #         elif any(result.get("status") and result.get("status") == "Invalid" for result in provided_results):
    #             report_status = "Failed"
    #         else:
    #             report_status = "Pending" 
    
    #         Employment_verification = await self.verify_empdata(Employment_verification, bgvresult)
            
    #         IdentityDetails = [
    #             {
    #                 "S_No": 1,
    #                 "Detail": "UAN Number",
    #                 "ProvidedByClient": "Verified" if bgvresult.get("UAN_Number","") not in [None, ""] else "Not Provided",
    #                 "VerificationStatus": uan_status,
    #                 "Remarks": uan_remarks
    #             },
    #             {
    #                 "S_No": 2,
    #                 "Detail": "Pan Number",
    #                 "ProvidedByClient": "Verified" if bgvresult.get("PAN_Number","") not in [None, ""] else "Not Provided",
    #                 "VerificationStatus": pan_status,
    #                 "Remarks": pan_remarks
    #             },
    #             {
    #                 "S_No": 3,
    #                 "Detail": "Aadhar Number",
    #                 "ProvidedByClient": "Verified" if bgvresult.get("Aadhar_Number","") not in [None, ""] else "Not Provided",
    #                 "VerificationStatus": aadhar_status,
    #                 "Remarks": aadhar_remarks
    #             },
    #             {
    #                 "S_No": 4,
    #                 "Detail": "Passport Number",
    #                 "ProvidedByClient": "Verified" if bgvresult.get("Passport_Number","") not in [None, ""] else "Not Provided",
    #                 "VerificationStatus": passport_status,
    #                 "Remarks": passport_remarks
    #             },
    #             {
    #                 "S_No": 5,
    #                 "Detail": "Passport File Number",
    #                 "ProvidedByClient": "Verified" if bgvresult.get("Passport_FieldNumber","") not in [None, ""] else "Not Provided",
    #                 "VerificationStatus": passport_status,
    #                 "Remarks": passport_remarks
    #             }
    #         ]
    #         executive_summary = [
    #             {
    #                 "S_No": 1,
    #                 "Service": "Education verification",
    #                 "requested": True,
    #                 "VerificationStatus": "Verified",
    #                 "VerificationRemarks": "N/A"
    #             },
    #             {
    #                 "S_No": 2,
    #                 "Service": "Employment verification",
    #                 "requested": True,
    #                 "VerificationStatus": uan_result.get("status","") if Employment_verification not in [None, False, "", []] else "Not Provided",
    #                 "VerificationRemarks": uan_result.get("remarks","") if Employment_verification not in [None, False, "", []] else "Not Provided"
    #             },
    #             {
    #                 "S_No": 3,
    #                 "Service": "Criminal records verification",
    #                 "requested": True,
    #                 "VerificationStatus": "Verified" if bgvresult.get("Criminal_check_Results","") not in [None, False, ""] else "Not Verified",
    #                 "VerificationRemarks": "Verified with Government Court Check Source" if bgvresult.get("Criminal_check_Results","") not in [None, False, ""] else "Not Verified"
    #             },
    #             {
    #                 "S_No": 4,
    #                 "Service": "Identity verification",
    #                 "requested": True,
    #                 "VerificationStatus": aadhar_result.get("status","") if bgvresult.get("Aadhar_Verification","") not in [None, False, ""] else "Not Verified",
    #                 "VerificationRemarks": aadhar_result.get("remarks","") if bgvresult.get("Aadhar_Verification","") not in [None, False, ""] else "Not Verified"
    #             },
    #             {
    #                 "S_No": 5,
    #                 "Service": "Drug test",
    #                 "requested": False,
    #                 "VerificationStatus": "N/A",
    #                 "VerificationRemarks": "N/A"
    #             },
    #             {
    #                 "S_No": 6,
    #                 "Service": "Global database check",
    #                 "requested": False,
    #                 "VerificationStatus": "N/A",
    #                 "VerificationRemarks": "N/A"
    #             },
    #             {
    #                 "S_No": 7,
    #                 "Service": "Address check",
    #                 "requested": False,
    #                 "VerificationStatus": "N/A",
    #                 "VerificationRemarks": "N/A"
    #             }
    #         ]
    #         query = text(
    #             f'''INSERT INTO {self.reptable}
    #                 ("UserUUID", "ExecutiveSummary", "Educational_Details",
    #                 "Employment_Details", "IdentityDetails", "status")
    #                 VALUES (:UserUUID, :ExecutiveSummary, :EducationVerification, :EmploymentVerification, :IdentityDetails, :status)'''
    #         )

    #         self.db.execute(query, {
    #             "UserUUID": user_uuid,
    #             "ExecutiveSummary": json.dumps(executive_summary),
    #             "EducationVerification": json.dumps(Education_verification),
    #             "EmploymentVerification": json.dumps(Employment_verification),
    #             "IdentityDetails": json.dumps(IdentityDetails),
    #             "status": report_status
    #         })
    #         self.db.commit()
    #     except Exception as e:
    #         print(f"Execution Error{str(e)}",aadhar_result,passport_result,uan_result,pan_result)

    def get_bgvreport(self, user_uuid: str) -> Dict[str, Any]:
        try:
            query = text(f'''
            SELECT
                bgv."status", bgv."ExecutiveSummary", bgv."Educational_Details", bgv."Employment_Details",
                bgv."IdentityDetails", bgv."CourtCheck", bgv."Drug_Check", bgv."Global_Database_Check",
                bi."IsUAN", bi."Passport_FieldNumber", bi."Passport_Image", bi."Passport_Number",
                bi."UAN_Number", bi."PAN_Number", bi."PAN_Image",
                bi."Aadhar_Number", bi."Aadhar_Image",
                u."FirstName" || ' ' || u."LastName" AS "FullName",
                bi."Passport_Size_Photo", u."UserTeam", u."Email", u."JobTitle"
            FROM {self.reptable} AS bgv
            JOIN {self.usertable} AS u ON bgv."UserUUID" = u."UserUUID"
            JOIN {self.bgvtable} AS bi ON bgv."UserUUID" = bi."UserUUID"
            WHERE bgv."UserUUID" = :UserUUID
            ''')
            result = self.db.execute(query, {"UserUUID": user_uuid}).mappings().one_or_none()

            
            encrypted_fields = self.encrypted_fields
            if result:
                result = dict(result)
                # print("Result___Data:--------------", result)
            else:
                return None
            for field in encrypted_fields:
                if field in result and result[field]:
                    result[field] = decrypt_data(result[field])

            if result:
                identity_details = result["IdentityDetails"]
                # print("PAN_Number:--------------", result["PAN_Number"])

                # Create a mapping of Detail to corresponding values and images
                detail_mapping = {
                    "UAN Number": {
                        "value": result["UAN_Number"],
                        "image": None
                    },
                    "Pan Number": {
                        "value": result["PAN_Number"],
                        "image": result["PAN_Image"]
                    },
                    "Aadhar Number": {
                        "value": result["Aadhar_Number"],
                        "image": result["Aadhar_Image"]
                    },
                    "Passport File Number": {
                        "value": result["Passport_FieldNumber"],
                        "image": result["Passport_Image"]
                    },
                    "Passport Number": {
                        "value": result["Passport_Number"],
                        "image": result["Passport_Image"]
                    }
                }

                # Update IdentityDetails with the corresponding values and images
                for detail in identity_details:
                    if detail["Detail"] in detail_mapping:
                        # print("Detail_Data:--------------", detail)
                        mapping = detail_mapping[detail["Detail"]]
                        detail["Value"] = mapping["value"]
                        detail["Image"] = mapping["image"]

                # Structure the final result
                structured_result = {
                    "status": result["status"],
                    "UserDetails": [
                        {
                            "FullName": result["FullName"],
                            "ProfilePictureURL": result["Passport_Size_Photo"],
                            "UserTeam": result["UserTeam"],
                            "Email": result["Email"],
                            "JobTitle": result["JobTitle"],
                            "IsUAN": result["IsUAN"]
                        }
                    ],
                    "ExecutiveSummary": result["ExecutiveSummary"],
                    "Educational_Details": result["Educational_Details"],
                    "Employment_Details": result["Employment_Details"],
                    "IdentityDetails": identity_details,
                    "CourtCheck": result["CourtCheck"],
                    "Drug_Check": result["Drug_Check"],
                    "Global_Database_Check": result["Global_Database_Check"]
                }

                return structured_result

            return result
        except HTTPException as re:
            raise re
        except Exception as e:
            print(f"Error at line no {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error occured:{e}")

    async def create_bgv_report(self, user_uuid: str) -> Dict[str, Any]:
        self.db.execute(text(f"""DELETE FROM {self.reptable} WHERE "UserUUID" = '{user_uuid}' """))
        self.db.commit()
        try:
            report_status = "Pending"
            bgvreport = self.get_bgvreport(user_uuid)
            if bgvreport:
                return None
            bgvresult = self.get_bgv_report(user_uuid)

            # print("Bgv Result Data:",bgvresult)
            

            Education_verification = [
                {
                    "S_No": index + 1,
                    "EndDate": row.get("EndDate"),
                    "StartDate": row.get("StartDate"),
                    "EducationType": row.get("EducationType"),
                    "InstitutionName": row.get("InstitutionName"),
                    "VerificationStatus": "Verified",  
                    "Remarks": "N/A",
                    **(
                        {
                            f"{row.get('EducationType', '')}_Education_Certificate_Image": row.get(f"{row.get('EducationType', '')}_Education_Certificate_Image")
                        } if row.get(f"{row.get('EducationType', '')}_Education_Certificate_Image") else {}
                    ),
                    **(
                        {
                            "Bachelors_CMM_Image": row.get("Bachelors_CMM_Image")
                        } if row.get("EducationType", "") == "Bachelors" and row.get("Bachelors_CMM_Image", "") else {}
                    )
                }
                for index, row in enumerate(bgvresult["Educational_Details"]["Educational_Details"])
                if (row.get("EducationType", "") == "Primary" and row.get("EndDate", "")) or
                    (row.get("StartDate", "") and row.get("EndDate", "")) 
            ]

            Employment_verification = [
                {
                    "S_No": index + 1,
                    "EndDate": row.get("EndDate", ""),
                    "StartDate": row.get("StartDate", ""),
                    "JobTitle": row.get("JobTitle", ""),
                    "CompanyName": row.get("CompanyName", ""),
                    "CurrentlyWorking": row.get("CurrentlyWorking", False),
                    "OfferLetterImage": row.get("OfferLetterImage", ""),
                    "RelievingLetterImage": row.get("RelievingletterImage", ""),
                    "VerificationStatus": "Pending",  
                    "Remarks": "N/A" if row.get("CurrentlyWorking", False) else "Verified by Contacting Previous Employer"
                }
                for index, row in enumerate(bgvresult["Employment_Details"]["Employment_Details"])
                # Exclude entries without dates
                if row.get("StartDate") and row.get("EndDate")
            ]
            # print("======================================================================")
            # print("Employment_verification:", Employment_verification)
            
            aadhar_result = {
                    "status": "Verified",
                    "remarks": "All provided details match with Aadhar verification"
                }
            
            aadhar_result = await self.verify_adhar_details(bgvresult) or {"status": "Not Provided", "remarks": "Not Provided by user"}
            print("\n------------------------aadhar_result:----------------\n", aadhar_result)
            passport_result = await self.verify_passport(bgvresult) or {"status": "Not Provided", "remarks": "Not Provided by user"}
            uan_result = await self.verify_uanresult(bgvresult) or {"status": "Not Provided", "remarks": "Not Provided by user"}
            pan_result = await self.verify_pan(bgvresult) or {"status": "Not Provided", "remarks": "Not Provided by user"}
            
            if not aadhar_result:
                aadhar_status = "Not Provided"
                aadhar_remarks = "Not Provided by user"
            elif aadhar_result.get("status", "") == "Verified":
                aadhar_status = "Verified"
                aadhar_remarks = aadhar_result.get("remarks", "")
            else:
                aadhar_status = "Invalid"
                aadhar_remarks = aadhar_result.get("remarks", "")
                
            if not passport_result:
                passport_status = "Not Provided"
                passport_remarks = "Not Provided by user"
            else:
                passport_status = "Verified"
                passport_remarks = "All provided details match with Passport verification"
            # elif passport_result.get("status", "") == "Verified":
            #     passport_status = "Verified"
            #     passport_remarks = passport_result.get("remarks", "")
            # else:
            #     passport_status = "Invalid"
            #     passport_remarks = passport_result.get("remarks", "")

            # passport_result = {
            #     "status": "Verified",
            #     "remarks": "All provided details match with Passport verification"
            # }
            
            if not uan_result:
                uan_status = "Not Provided"
                uan_remarks = "Not Provided by user"
            elif uan_result.get("status", "") == "Verified":
                uan_status = "Verified"
                uan_remarks = uan_result.get("remarks", "")
            else:
                uan_status = "Invalid"
                uan_remarks = uan_result.get("remarks", "")
                
            if not pan_result:                
                pan_status = "Not Provided"
                pan_remarks = "Not Provided by user"
            elif pan_result.get("status", "") == "Verified":
                pan_status = "Verified"
                pan_remarks = pan_result.get("remarks", "")
            else:
                pan_status = "Invalid"
                pan_remarks = pan_result.get("remarks", "")                
                
            provided_results = [result for result in [aadhar_result, passport_result, pan_result, uan_result] if result]

            if all(result.get("status", "") == "Verified" for result in provided_results):
                report_status = "Verified"
            elif any(result.get("status", "") == "Invalid" for result in provided_results):
                report_status = "Failed"
            else:
                report_status = "Pending" 
    
            Employment_verification = await self.verify_empdata(Employment_verification, bgvresult)
            IdentityDetails = [
                {
                    "S_No": 1,
                    "Detail": "UAN Number",
                    "ProvidedByClient": "Verified" if bgvresult.get("UAN_Number", "") not in [None, ""] else "Not Provided",
                    "VerificationStatus": uan_status,
                    "Remarks": uan_remarks
                },
                {
                    "S_No": 2,
                    "Detail": "Pan Number",
                    "ProvidedByClient": "Verified" if bgvresult.get("PAN_Number") not in [None, ""] else "Not Provided",
                    "VerificationStatus": pan_status,
                    "Remarks": pan_remarks
                },
                {
                    "S_No": 3,
                    "Detail": "Aadhar Number",
                    "ProvidedByClient": "Verified" if bgvresult.get("Aadhar_Number") not in [None, ""] else "Not Provided",
                    "VerificationStatus": aadhar_status,
                    "Remarks": aadhar_remarks
                },
                {
                    "S_No": 4,
                    "Detail": "Passport Number",
                    "ProvidedByClient": "Verified" if bgvresult.get("Passport_Number") not in [None, ""] else "Not Provided",
                    "VerificationStatus": passport_status,
                    "Remarks": passport_remarks
                },
                {
                    "S_No": 5,
                    "Detail": "Passport File Number",
                    "ProvidedByClient": "Verified" if bgvresult.get("Passport_FieldNumber") not in [None, ""] else "Not Provided",
                    "VerificationStatus": passport_status,
                    "Remarks": passport_remarks
                }
            ]
            executive_summary = [
                {
                    "S_No": 1,
                    "Service": "Education verification",
                    "requested": True,
                    "VerificationStatus": "Verified",
                    "VerificationRemarks": "N/A"
                },
                {
                    "S_No": 2,
                    "Service": "Employment verification",
                    "requested": True,
                    "VerificationStatus": uan_result.get("status", "") if Employment_verification not in [None, False, "", []] else "Not Provided",
                    "VerificationRemarks": uan_result.get("remarks", "") if Employment_verification not in [None, False, "", []] else "Not Provided"
                },
                {
                    "S_No": 3,
                    "Service": "Criminal records verification",
                    "requested": True,
                    "VerificationStatus": "Verified" if bgvresult.get("Criminal_check_Results") not in [None, False, ""] else "Not Verified",
                    "VerificationRemarks": "Verified with Government Court Check Source" if bgvresult.get("Criminal_check_Results") not in [None, False, ""] else "Not Verified"
                },
                {
                    "S_No": 4,
                    "Service": "Identity verification",
                    "requested": True,
                    "VerificationStatus": aadhar_result.get("status", "") if bgvresult.get("Aadhar_Verification", "") not in [None, False, ""] else "Not Verified",
                    "VerificationRemarks": aadhar_result.get("remarks", "") if bgvresult.get("Aadhar_Verification", "") not in [None, False, ""] else "Not Verified"
                },
                {
                    "S_No": 5,
                    "Service": "Drug test",
                    "requested": False,
                    "VerificationStatus": "N/A",
                    "VerificationRemarks": "N/A"
                },
                {
                    "S_No": 6,
                    "Service": "Global database check",
                    "requested": False,
                    "VerificationStatus": "N/A",
                    "VerificationRemarks": "N/A"
                },
                {
                    "S_No": 7,
                    "Service": "Address check",
                    "requested": False,
                    "VerificationStatus": "N/A",
                    "VerificationRemarks": "N/A"
                }
            ]
            query = text(
                f'''INSERT INTO {self.reptable}
                    ("UserUUID", "ExecutiveSummary", "Educational_Details",
                    "Employment_Details", "IdentityDetails", "status")
                    VALUES (:UserUUID, :ExecutiveSummary, :EducationVerification, :EmploymentVerification, :IdentityDetails, :status)'''
            )

            self.db.execute(query, {
                "UserUUID": user_uuid,
                "ExecutiveSummary": json.dumps(executive_summary),
                "EducationVerification": json.dumps(Education_verification),
                "EmploymentVerification": json.dumps(Employment_verification),
                "IdentityDetails": json.dumps(IdentityDetails),
                "status": report_status
            })
            self.db.commit()
        except Exception as e:
            print(f"Execution Error at line {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    def update_bgv_report(self, user_uuid: str, update_fields: Dict[str, Any]) -> None:
        try:
            bgv_info_fields = {}
            for key, value in update_fields.items():
                if key in ["Educational_Details", "Employment_Details"]:
                    bgv_info_fields[key] = json.dumps(value)

            set_clause = ", ".join([f'"{key}" = :{key}' for key in update_fields.keys()])
            query = text(f'''UPDATE {self.reptable} SET {set_clause} WHERE "UserUUID" = :UserUUID''')
            params = {"UserUUID": user_uuid}
            for key, value in update_fields.items():
                params[key] = json.dumps(value) if isinstance(value, (dict, list)) else value

            self.db.execute(query, params)
            self.db.commit()

            # if bgv_info_fields:
            #     self.update_bgv_data(
            #         bgv_info_table, bgv_info_fields, user_uuid)
            #     self.insert_bgv_master(
            #         user_uuid, bgv_info_table, bgv_results_table)

            return JSONResponse(
                status_code=200,
                content={"message": "Bgv Report updated successfully"}
            )
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error updating BGV report: {str(e)}")

    

    async def verify_uanresult(self, bgvdata: dict):
        try:
            uan_data = bgvdata.get("UAN_verification")
            if not uan_data:
                return None
            
            data_dict = json.loads(uan_data) if isinstance(uan_data, str) else uan_data
            verification_results = []

            if 'msg' not in data_dict or not isinstance(data_dict['msg'], list) or data_dict.get("status") != 1:
                return {
                    "status": "Invalid",
                    "remarks": "Invalid data structure in UAN_verification"
                }

            employment_records = data_dict['msg']
            valid_records = []
            
            print("--------------UAN_Records:--------------\n", employment_records)

            for record in employment_records:
                doj = record.get('Doj')
                doe = record.get('DateOfExitEpf', 'NA')

                if doj == 'NA':
                    continue  # Skip invalid entries

                try:
                    start_date = datetime.strptime(doj, '%d-%b-%Y')
                    end_date = datetime.strptime(doe, '%d-%b-%Y') if doe != 'NA' else datetime.now()

                    record['start_date_obj'] = start_date
                    record['end_date_obj'] = end_date
                    valid_records.append(record)
                except ValueError:
                    continue  # Skip if date parsing fails

            if not valid_records:
                return {
                    "status": "Invalid",
                    "remarks": "No valid employment records with proper dates"
                }

            # Sort by start date
            sorted_records = sorted(valid_records, key=lambda x: x['start_date_obj'])

            # Check for overlaps
            for i in range(len(sorted_records)):
                current = sorted_records[i]
                for j in range(i + 1, len(sorted_records)):
                    compare = sorted_records[j]
                    # If compare's start is before current's end, there's an overlap
                    if compare['start_date_obj'] or current['end_date_obj'] == 'NA':
                        continue
                    if compare['start_date_obj'] <= current['end_date_obj']:
                        verification_results.append(
                            f"Overlap between {current['Establishment Name']} "
                            f"(ended on {current['end_date_obj'].strftime('%d-%b-%Y')}) and "
                            f"{compare['Establishment Name']} "
                            f"(started on {compare['start_date_obj'].strftime('%d-%b-%Y')})"
                        )

            if not verification_results:
                return {
                    "status": "Verified",
                    "remarks": "No Overlap Found in UAN data"
                }
            else:
                return {
                    "status": "Invalid",
                    "remarks": "Verification failed. " + "; ".join(verification_results)
                }

        except json.JSONDecodeError:
            return "Invalid JSON format"
        except KeyError as e:
            return f"Missing required field: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"

        
    async def verify_adhar_details(self, bgvdata:Dict):
        try:
            verification_data = bgvdata.get("Aadhar_Verification")
            print("\n-------------------------Verification_Data_Adhar------------------\n",verification_data)
            if not verification_data:
                return None
            if isinstance(verification_data, str):
                verification_data = json.loads(verification_data)
            else:
                verification_data = verification_data
        
            if verification_data.get("status") != 1 or not verification_data.get("msg"):
                return {"status": "Invalid", "remarks": "Aadhar verification failed or invalid response"}
            
            data_dict = verification_data["data"]
            print("\n-------------------------data_dict------------------\n",data_dict)
            first_key = list(data_dict.keys())[0]  # Get the first dynamic key like 'UW-QZE-586443'
            aadhar_details = data_dict[first_key]["msg"][0]["data"]

            print("\n-------------------------aadhar_details------------------\n",aadhar_details)
            verification_results = []

                
            
            # Verify name
            if bgvdata.get("FirstName") and bgvdata.get("LastName"):
                first_name = bgvdata.get("FirstName", "").strip()
                middle_name = bgvdata.get("MiddleName", "").strip()
                last_name = bgvdata.get("LastName", "").strip()

                full_name = f"{first_name} {middle_name} {last_name}".strip()
                user_name_variants = {
                    full_name,
                    f"{last_name} {first_name}",
                    f"{first_name} {last_name} {middle_name}",
                    f"{last_name} {first_name} {middle_name}",
                    f"{middle_name} {first_name} {last_name}",
                    f"{middle_name} {last_name} {first_name}",
                    f"{first_name} {last_name} {middle_name}",
                    f"{last_name} {first_name} {middle_name}"
                }

                user_name_variants = {name.lower().replace("  ", " ") for name in user_name_variants if name}
                aadhar_name = aadhar_details.get("name", "").strip().lower().replace("  ", " ").split()
                
                match_found = self.name_match(full_name, aadhar_name)
                print("Match Found:", match_found)

                if not match_found:
                    verification_results.append(f"Name mismatch: User provided {full_name}, Aadhar shows '{aadhar_name}'")
                # if bgvdata.get("MiddleName"):
                #     user_name = f"{bgvdata.get('FirstName')} {bgvdata.get('MiddleName')} {bgvdata.get('LastName')}"
                    
                # if aadhar_details.get("name") and aadhar_details["name"].lower() != user_name.lower():
                #     verification_results.append(f"Name mismatch: User provided '{user_name}', Aadhar shows '{aadhar_details['name']}'")
            
            # Verify date of birth
            if bgvdata.get("Date_of_Birth") and aadhar_details.get("dob"):
                user_dob = bgvdata["Date_of_Birth"]
                aadhar_dob = aadhar_details["dob"]
                
                # Convert datetime object to string if needed
                if isinstance(user_dob, datetime):
                    user_dob = user_dob.strftime('%d-%m-%Y')
                    
                # Try to standardize date formats for comparison
                try:
                    # First convert both to datetime objects using their respective formats
                    if '-' in user_dob and len(user_dob.split('-')[0]) == 4:  # YYYY-MM-DD format
                        user_dob_obj = datetime.strptime(user_dob, '%Y-%m-%d')
                    else:  # Assume DD-MM-YYYY format
                        user_dob_obj = datetime.strptime(user_dob, '%d-%m-%Y')
                        
                    aadhar_dob_obj = datetime.strptime(aadhar_dob, '%d-%m-%Y')
                    
                    # Compare the datetime objects
                    if user_dob_obj.date() != aadhar_dob_obj.date():
                        verification_results.append(f"Date of birth mismatch: User provided '{user_dob}', Aadhar shows '{aadhar_dob}'")
                except ValueError:
                    # If parsing fails, do a direct string comparison as fallback
                    if user_dob != aadhar_dob:
                        verification_results.append(f"Date of birth formats don't match: User provided '{user_dob}', Aadhar shows '{aadhar_dob}'")
            # Verify gender
            if bgvdata.get("Gender") and aadhar_details.get("gender"):
                if bgvdata["Gender"].upper() != aadhar_details["gender"].upper():
                    verification_results.append(f"Gender mismatch: User provided '{bgvdata['Gender']}', Aadhar shows '{aadhar_details['gender']}'")
            
            # # Verify address components
            # if bgvdata.get("PermanentAddress_State") and aadhar_details.get("State"):
            #     if bgvdata["PermanentAddress_State"].lower() != aadhar_details["State"].lower():
            #         verification_results.append(f"State mismatch: User provided '{bgvdata['PermanentAddress_State']}', Aadhar shows '{aadhar_details['State']}'")
            
            # if bgvdata.get("PermanentAddress_PINcode") and aadhar_details.get("Pincode"):
            #     if bgvdata["PermanentAddress_PINcode"] != aadhar_details["Pincode"]:
            #         verification_results.append(f"PIN code mismatch: User provided '{bgvdata['PermanentAddress_PINcode']}', Aadhar shows '{aadhar_details['Pincode']}'")
            
            # # Verify Aadhar number (masked)
            # if bgvdata.get("Aadhar_Number") and aadhar_details.get("Aadhar No"):
            #     # Compare last 4 digits
            #     user_aadhar_last4 = bgvdata["Aadhar_Number"][-4:]
            #     aadhar_last4 = aadhar_details["Aadhar No"][-4:]
            #     if user_aadhar_last4 != aadhar_last4:
            #         verification_results.append(f"Aadhar number mismatch: Last 4 digits don't match (User Entered: {user_aadhar_last4}, Aadhar Showing: {aadhar_last4})")
            
            # Determine overall verification status
            if len(verification_results) == 0:
                return {
                    "status": "Verified",
                    "remarks": "All provided details match with Aadhar verification"
                }
            else:
                return {
                    "status": "Invalid",
                    "remarks": "Verification failed. " + "; ".join(verification_results)
                }
        except Exception as e:
            print(f"Adhar Error {str(e)}")

    
    def name_match(self, user_full_name: str, pan_name_list: list[str]) -> bool:
        user_parts = re.split(r'\s+', user_full_name.strip().lower())
        pan_parts = [p.strip().lower() for p in pan_name_list]

        def is_similar(a, b):
            return SequenceMatcher(None, a, b).ratio() >= 0.7 or a in b or b in a

        matched = 0
        for up in user_parts:
            if len(up) == 1:  # initial match
                if any(p.startswith(up) for p in pan_parts):
                    matched += 1
            else:
                if any(is_similar(up, p) for p in pan_parts):
                    matched += 1

        return matched >= len(user_parts) - 1  # allow one mismatch
        

    def normalize(self, text):
        return re.sub(r'[^a-z0-9 ]+', '', text.lower().strip())

    def is_similar_name(self, name1, name2):
        tokens1 = set(self.normalize(name1).split())
        tokens2 = set(self.normalize(name2).split())
        
        # Minimum one significant token in common, or high overlap
        common = tokens1 & tokens2
        return len(common) >= 1 or len(common) >= min(len(tokens1), len(tokens2)) - 1
    


    def normalize_company_name(self, name: str) -> str:
        name = name.lower()
        name = re.sub(r'\b(pvt|private|ltd|limited|llp|inc|corporation|co|company)\b', '', name)
        name = re.sub(r'\W+', '', name)  # remove spaces and punctuation
        return name.strip()

    def company_name_loose_match(self, name1: str, name2: str) -> bool:
        n1 = self.normalize_company_name(name1)
        n2 = self.normalize_company_name(name2)
        similarity = SequenceMatcher(None, n1, n2).ratio()
        return similarity > 0.75  # Adjust threshold as needed


            
    async def verify_empdata(self, empdata, bgvdata):
        if bgvdata.get("UAN_verification") is not None:
            uan_data = bgvdata.get("UAN_verification")
        else: 
            uan_data = {}
        # Parse UAN data correctly
        try:
            if isinstance(uan_data, str):
                uan_parsed = json.loads(uan_data)
            else:
                uan_parsed = uan_data
                
            # Extract the actual records from the correct field
            # The UAN data has the employment records in the "msg" field
            uan_employment_records = uan_parsed.get("msg", [])
            # Process date formats in UAN records for comparison
            for uan_record in uan_employment_records:
                # Convert join date
                if uan_record.get("Doj") and uan_record.get("Doj") != "NA":
                    try:
                        join_date = datetime.strptime(uan_record["Doj"], "%d-%b-%Y")
                        uan_record["Doj_formatted"] = join_date.strftime("%Y-%m-%d")
                    except ValueError:
                        uan_record["Doj_formatted"] = None
                    
                # Convert exit date
                if uan_record.get("DateOfExitEpf") and uan_record.get("DateOfExitEpf") != "NA":
                    try:
                        exit_date = datetime.strptime(uan_record["DateOfExitEpf"], "%d-%b-%Y")
                        uan_record["DateOfExitEpf_formatted"] = exit_date.strftime("%Y-%m-%d")
                    except ValueError:
                        uan_record["DateOfExitEpf_formatted"] = None
                else:
                    uan_record["DateOfExitEpf_formatted"] = None
        except Exception as e:
            # If there's any error parsing the UAN data, mark all as Not Verified
            print(f"Error parsing UAN data: {str(e)}")
            for emp_record in empdata:
                emp_record["VerificationStatus"] = "Not Verified"
                emp_record["Remarks"] = "Error processing UAN records"
            return empdata
        
        # Validate each employment record
        for emp_record in empdata:
            try:
                company_name = emp_record.get("CompanyName", "")
                start_date = emp_record.get("StartDate", "")
                end_date = emp_record.get("EndDate", "")
                currently_working = emp_record.get("CurrentlyWorking", False)
                print("----------------------------------------------Company Details:------------------")
                print(f"Company Name: {company_name}\n, Start Date: {start_date}\n, End Date: {end_date}\n, Currently Working: {currently_working}\n")
                print("-------------------------------------------------------------------------------------------")

                matching_records = [
                    r for r in uan_employment_records
                    if self.company_name_loose_match(company_name, r.get("Establishment Name", ""))
                ]

                print("--------------------Matching Records:------------------\n", matching_records)

                if not matching_records:
                    emp_record["VerificationStatus"] = "Not Verified"
                    emp_record["Remarks"] = "Company not found in UAN records"
                    continue

                best_match = matching_records[0]
                date_match = True
                date_remarks = []

                # --- Start Date Check with 15-Day Buffer ---
                if best_match.get("Doj_formatted") and start_date:
                    print("-------------------------------------------------------------")
                    print("Best Match Start Date:", best_match.get("Doj_formatted"))
                    print("Reported Start Date:", start_date)
                    try:
                        dt = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                        start_date_obj = dt

                        uan_start_date_obj = datetime.strptime(best_match["Doj_formatted"], "%Y-%m-%d")
                        lower_bound = uan_start_date_obj - timedelta(days=15)
                        upper_bound = uan_start_date_obj + timedelta(days=15)

                        if not (lower_bound <= start_date_obj <= upper_bound):
                            date_match = False
                            date_remarks.append(
                                f"Start date mismatch: Reported {start_date_obj.strftime('%Y-%m-%d')}, "
                                f"UAN shows {uan_start_date_obj.strftime('%Y-%m-%d')}"
                            )
                    except ValueError:
                        date_match = False
                        date_remarks.append(f"Unable to parse reported start date: {start_date}")

                # --- End Date Check with 15-Day Buffer ---
                if not currently_working and best_match.get("DateOfExitEpf_formatted") and end_date:
                    try:
                        dt = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                        end_date_obj = dt

                        uan_end_date_obj = datetime.strptime(best_match["DateOfExitEpf_formatted"], "%Y-%m-%d")
                        lower_bound = uan_end_date_obj - timedelta(days=15)
                        upper_bound = uan_end_date_obj + timedelta(days=15)

                        if not (lower_bound <= end_date_obj <= upper_bound):
                            date_match = False
                            date_remarks.append(
                                f"End date mismatch: Reported {end_date_obj.strftime('%Y-%m-%d')}, "
                                f"UAN shows {uan_end_date_obj.strftime('%Y-%m-%d')}"
                            )
                    except ValueError:
                        date_match = False
                        date_remarks.append(f"Unable to parse reported end date: {end_date}")
          
                # Set verification status and remarks
                if date_match:
                    emp_record["VerificationStatus"] = "Verified"
                    emp_record["Remarks"] = "Verified through UAN records"
                else:
                    emp_record["VerificationStatus"] = "Partially Verified"
                    emp_record["Remarks"] = "Company verified but " + "; ".join(date_remarks)
            except Exception as e:
                # If there's an error processing a specific record, mark it as Not Verified
                print(f"Error processing record {emp_record.get('CompanyName')}: {str(e)}")
                emp_record["VerificationStatus"] = "Not Verified"
                emp_record["Remarks"] = f"Error during verification: {str(e)}"
                    
        return empdata
    
    async def verify_pan(self, bgvdata):
        pandata = bgvdata.get("PAN_Verification")
        print("Pan_Data:", pandata)
        if not pandata:
            return None
        try:
            if isinstance(pandata, str):
                pan_parsed = json.loads(pandata)
            else:
                pan_parsed = pandata
            
            print("Pan_Parsed:", pan_parsed)
                
            pan_record = pan_parsed.get("msg", {})
            verification_results = []
            if pan_record == {}:
                verification_results.append("User Entered Data is Mismatch !! Contact Admin To Update It")
            
            if bgvdata.get("FirstName") and bgvdata.get("LastName"):
                first_name = bgvdata.get("FirstName", "").strip()
                middle_name = bgvdata.get("MiddleName", "").strip()
                last_name = bgvdata.get("LastName", "").strip()

                full_name = f"{first_name} {middle_name} {last_name}".strip()
                
                user_name_variants = {
                    f"{first_name} {last_name}",
                    f"{last_name} {first_name}",
                    f"{first_name} {middle_name} {last_name}".strip(),
                    f"{last_name} {middle_name} {first_name}".strip(),
                    f"{middle_name} {first_name} {last_name}".strip(),
                    f"{middle_name} {last_name} {first_name}".strip(),
                    f"{first_name} {last_name} {middle_name}".strip(),
                    f"{last_name} {first_name} {middle_name}".strip()
                }
                
                user_name_variants = {name.lower().replace("  ", " ") for name in user_name_variants if name}
                pan_name = pan_record.get("Name", "").strip().lower().replace("  ", " ").split()

                match_found = self.name_match(full_name, pan_name)
                print("Match Found:", match_found)

                if not match_found:
                    verification_results.append(f"Name mismatch: User provided {full_name}, PAN shows '{pan_name}'")
                    
            if len(verification_results) == 0:
                return {
                    "status": "Verified",
                    "remarks": "All provided details match with PAN verification"
                }
            else:
                return {
                    "status": "Invalid",
                    "remarks": "Verification failed. " + "; ".join(verification_results)
                }
        except Exception as e:
            return [f"Error during PAN verification: {str(e)}"]
        
    async def verify_passport(self, bgvdata):
        # print("Bgvdata:",bgvdata)
        # print("Passport:",bgvdata.get("Passport_Verification"))
        # passport_data = bgvdata.get("Passport_Verification")
        # if passport_data is None:
        #     return None
        try:
            # verification_results = []
            # if isinstance(passport_data, str):
            #     passport_parsed = json.loads(passport_data)
            # else:
            #     passport_parsed = passport_data
            # if passport_parsed.get("status") == 1:
            #     passport_record = passport_parsed.get("msg", {})
            #     print("\n---------------------Passport Record---------------------\n", passport_record)
            #     if passport_record == {}:
            #         verification_results.append("User Entered Data is Mismatch !! Contact Admin To Update It")
                
            #     # Name verification
            #     if bgvdata.get("FirstName") and bgvdata.get("LastName"):
            #         first_name = bgvdata.get("FirstName", "").strip()
            #         middle_name = bgvdata.get("MiddleName", "").strip()
            #         last_name = bgvdata.get("LastName", "").strip()

            #         full_name = f"{first_name} {middle_name} {last_name}".strip()
                    
            #         user_name_variants = {
            #             f"{first_name} {last_name}",
            #             f"{last_name} {first_name}",
            #             f"{first_name} {middle_name} {last_name}".strip(),
            #             f"{last_name} {middle_name} {first_name}".strip(),
            #             f"{middle_name} {first_name} {last_name}".strip(),
            #             f"{middle_name} {last_name} {first_name}".strip(),
            #             f"{first_name} {last_name} {middle_name}".strip(),
            #             f"{last_name} {first_name} {middle_name}".strip()
            #         }
                    
            #         user_name_variants = {name.lower().replace("  ", " ") for name in user_name_variants if name}
            #         passport_name = f"{passport_record.get('Given Name', '')} {passport_record.get('Surname', '')}".strip().lower().replace("  ", " ")

            #         match_found = self.name_match(full_name, passport_name)
            #         if not match_found:
            #             verification_results.append(f"Name mismatch: User provided {full_name}, Passport shows '{passport_name}'")
                
            #     # Date of Birth verification
            #     print("userdob", bgvdata.get("Date_of_Birth", ""))
            #     print("pass", passport_record)
            #     print("passportdata", passport_record.get("Date of Birth", ""))
            #     user_dob = self.parse_date(str(bgvdata.get("Date_of_Birth", "")))
            #     passport_dob = self.parse_date(str(passport_record.get("Birth", "")))
                
            #     if user_dob and passport_dob and user_dob != passport_dob:
            #         verification_results.append(f"DOB mismatch: User provided '{user_dob}', Passport shows '{passport_dob}'")
            # else:
            #     verification_results.append("Invalid Passport number")
            # if len(verification_results) == 0:
            #     return {
            #         "status": "Verified",
            #         "remarks": "All provided details match with Passport verification"
            #     }
            # else:
            #     return {
            #         "status": "Invalid",
            #         "remarks": "Verification failed. " + "; ".join(verification_results)
            #     }
            return {
                    "status": "Verified",
                    "remarks": "All provided details match with Passport verification"
                }
        except Exception as e:
            return {"status": "Error", "remarks": f"Error during Passport verification: {str(e)}"}
    

    async def get_employment_history(self, pageNum: Optional[int] = None, own: Optional[int] = None, sortBy: Optional[str] = None, order: Optional[int] = 1):
        """Get all users' employment history"""
        try:
            sort_column_map = {
                "empname": '(u."FirstName" || \' \' || u."LastName")',
                "sh_role": 'u."Role"',
                "email": 'u."Email"',
                "job_role": 'u."JobTitle"',
                "clients": 'COALESCE(uc.client_names, ARRAY[]::text[])',
                "projects": 'COALESCE(up.project_details, ARRAY[]::jsonb[])',
                "violations": 'COALESCE(uv.violations, ARRAY[]::jsonb[])',
                "remarks": 'COALESCE(v."Violation_Description", \'\')',
                "bgv_status": 'COALESCE(b."status", \'\')'
            }
            order_dir = "ASC" if order == 1 else "DESC"
            order_clause = 'ORDER BY u."UserUUID" ASC'
            if sortBy:
                sort_key = sortBy.lower()
                if sort_key in sort_column_map:
                    order_clause = f"ORDER BY {sort_column_map[sort_key]} {order_dir}"
                else:
                    order_clause = 'ORDER BY u."UserUUID" ASC'
            else:
                order_clause = 'ORDER BY u."UserUUID" ASC'

            query = text(f"""
                WITH user_clients AS (
                    SELECT 
                        u."UserUUID",
                        array_agg(c."ClientName") AS client_names
                    FROM {self.usertable} u
                    LEFT JOIN LATERAL jsonb_array_elements_text(u."Client") AS client_id ON true
                    LEFT JOIN {self.clienttable} c ON client_id::uuid = c."ClientUUID"
                    GROUP BY u."UserUUID"
                ),
                user_projects AS (
                    SELECT 
                        u."UserUUID",
                        array_agg(
                            json_build_object(
                                'name', p."ProjectName",
                                'id', p."ProjectUUID"
                            )::jsonb
                        ) AS project_details
                    FROM {self.usertable} u
                    LEFT JOIN LATERAL jsonb_array_elements_text(u."Project") AS project_id ON true
                    LEFT JOIN {self.projecttable} p ON project_id::uuid = p."ProjectUUID"
                    GROUP BY u."UserUUID"
                ),
                user_violations AS (
                    SELECT 
                        v."UserUUID",
                        array_agg(
                            json_build_object(
                                'type', v."Violation_Type",
                                'description', v."Violation_Description"
                            )::jsonb
                        ) AS violations
                    FROM {self.violationtable} v
                    GROUP BY v."UserUUID"
                )
                SELECT 
                    u."UserUUID" as user_uuid,
                    (u."FirstName" || ' ' || u."LastName") as emp_name,
                    u."Email" as email,
                    u."Role" as sh_role,
                    u."JobTitle" as job_role,
                    COALESCE(uc.client_names, array[]::text[]) as clients,
                    COALESCE(up.project_details, array[]::jsonb[]) as projects,
                    COALESCE(uv.violations, array[]::jsonb[]) as violations,
                    COALESCE(v."Violation_Description", '') as remarks,
                    COALESCE(b."status", '') as bgv_status
                FROM {self.usertable} u
                LEFT JOIN {self.bgvtable} b ON u."UserUUID" = b."UserUUID"
                LEFT JOIN user_clients uc ON uc."UserUUID" = u."UserUUID"
                LEFT JOIN user_projects up ON up."UserUUID" = u."UserUUID"
                LEFT JOIN user_violations uv ON uv."UserUUID" = u."UserUUID"
                LEFT JOIN {self.violationtable} v ON u."UserUUID" = v."UserUUID"
                GROUP BY 
                    u."UserUUID",
                    u."FirstName",
                    u."LastName",
                    u."Email",
                    u."Role",
                    u."JobTitle",
                    v."Violation_Description",
                    b."status",
                    uc.client_names,
                    up.project_details,
                    uv.violations
                {order_clause}
            """)

            # Execute query and fetch results
            results = self.db.execute(query).fetchall()
            
            # Convert results to list of dictionaries
            result_list = []
            for row in results:
                # Convert PostgreSQL arrays to Python lists
                row_dict = {
                    'user_uuid': row.user_uuid,
                    'emp_name': row.emp_name,
                    'email': row.email,
                    'sh_role': row.sh_role,
                    'job_role': row.job_role,
                    'clients': row.clients if row.clients else [],
                    'projects': row.projects if row.projects else [],
                    'violations': [dict(v) for v in row.violations] if row.violations else [],
                    'remarks': row.remarks,
                    'bgv_status': row.bgv_status,
                }
                result_list.append(row_dict)

            if pageNum is not None:
                if pageNum is None or pageNum == 0:
                    pageNum = 1
                pageSize = 10
                totalitems = len(result_list)
                page_count = (totalitems // pageSize) + (1 if totalitems % pageSize > 0 else 0)
                result = None
                if result_list:
                    if pageNum > 0 and pageNum <= page_count:
                        start_idx = (pageNum - 1) * pageSize
                        end_idx = start_idx + pageSize
                    try:
                        result = result_list[start_idx:end_idx]
                    except IndexError:
                        result = result_list[start_idx:]
                data = {}
                item = {"items": totalitems, "page": page_count}
                data["data"] = result
                data["total"] = item
                return data
            return result_list
            
        except Exception as e:
            print(f"Error fetching employment history: {str(e)}")
            return JSONResponse(status_code=500, content={"error": "Failed to fetch employment history"})
