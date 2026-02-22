import requests
from fastapi import HTTPException, status
import os
from dotenv import load_dotenv
load_dotenv()
class MicrosoftUserOnboarding:
    def __init__(self):
        self.tenant_id = os.environ.get('MS_TENANT_ID')
        self.client_id = os.environ.get('MS_CLIENT_ID')
        self.client_secret = os.environ.get('MS_SECRET_ID')
        self.graph_api_base_url = f"https://graph.microsoft.com/v1.0"

    def _get_access_token(self):
        """
        Get an OAuth2 access token from Microsoft Identity platform.
        """
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }

        response = requests.post(url, headers=headers, data=body)
        if response.status_code != 200:
            return error.error("Failed to obtain access token from Microsoft.", 400, "Access Token")
        return response.json()['access_token']

    def create_user(self, user_data: dict):
        """
        Create a user in Microsoft Azure AD.
        """
        access_token = self._get_access_token()
        url = f"{self.graph_api_base_url}/users"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=user_data)
        if response.status_code != 201:
            return error.error("Failed to create user in Microsoft Organization", 400, "User Creation")
        return response.json()

    def assign_license(self, user_id: str, licenses: dict):
        """
        Assign a license (like Exchange Online) to a user.
        """
        access_token = self._get_access_token()
        url = f"{self.graph_api_base_url}/users/{user_id}/assignLicense"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=licenses)
        if response.status_code != 200:
            return error.error("Failed to assign license to user", 400, "License Assignment")
        return response.json()

    def add_user_to_group(self, user_id: str, group_id: str):
        """
        Add a user to a group (e.g., for Outlook, SharePoint).
        """
        access_token = self._get_access_token()
        url = f"{self.graph_api_base_url}/groups/{group_id}/members/$ref"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        data = {
            "@odata.id": f"{self.graph_api_base_url}/directoryObjects/{user_id}"
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 204:
            return error.error("Failed to add user to group", 400, "Group Assignment")
        return response.status_code

    def onboard_user(self, data: dict):
        org_email = f"{data['User_Firstname'].lower()}@blackrockitsolutions.com"
        microsoft_user = {
            "accountEnabled": True,
            "displayName": f"{data['User_Firstname']} {data['User_Lastname']}",
            "mailNickname": data['User_Firstname'].lower(),
            "userPrincipalName": org_email,
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": "SecurePassword123!"  
            }
        }
        created_user = self.create_user(microsoft_user)
        user_id = created_user["id"]

        # Step 2: Assign licenses 
        licenses = {
            "addLicenses": [
                {"skuId": "exchange-online-sku-id"}  # Replace with your actual SKU ID
            ],
            "removeLicenses": []
        }
        self.assign_license(user_id, licenses)

        # Step 3: Assign user to required products
        product_results = {}
        products = ["outlook-group-id", "sharepoint-group-id", "teams-group-id"]
        for product_group_id in products:
            try:
                self.add_user_to_group(user_id, product_group_id)
                product_results[product_group_id] = "Successfully added"
            except Exception as e:
                product_results[product_group_id] = f"Failed to add: {e}"

        return {
            "message": "User onboarded successfully",
            "work_email": org_email,
            "product_assignments": product_results
        }
