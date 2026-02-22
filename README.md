# SaciaHub API 🚀

**SaciaHub** is a modern HR and Workforce Management Platform built with FastAPI and MySQL. It offers features like multi-tenant support, timesheet tracking, role-based access, and more.

---

## ✨ Introduction

SaciaHub helps companies manage their workforce digitally. The goal is to simplify tasks like timesheet tracking, user role management, and employee operations using a secure and scalable API-driven system.

---

## 🚀 Getting Started

### ✅ Prerequisites

* Python 3.12.5 or higher
* MySQL Server installed and running
* [Poetry](https://python-poetry.org/) (recommended) or `pip`

### 🔧 Installation

1. **Clone the repository**

   ```bash
   git clone https://dev.azure.com/britsdevapps/SaciaHub/_git/Dev_Api_SaciaHub
   cd Dev_Api_SaciaHub
   ```

2. **Create and activate a virtual environment**

   ```bash
   # Windows
   python -m venv env
   .\env\Scripts\activate

   # Linux/Mac
   python3 -m venv env
   source env/bin/activate
   ```

3. **Install dependencies**

   ```bash
   poetry install
   # OR
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory and add necessary environment variables like DB credentials, secret key, etc.

5. **Run the application**

   ```bash
   uvicorn App.main:app --reload
   ```

6. **Access the API**
   Navigate to [https://devapi.saciahub.com/docs#/](https://devapi.saciahub.com/docs#/) to access Swagger UI documentation.

7. **Access the Redoc**
   Navigate to [https://devapi.saciahub.com/redoc](https://devapi.saciahub.com/redoc) to access ReDoc documentation.

---

## 🧪 Build and Test

Run the application in development mode using:

```bash
uvicorn App.main:app --reload
```

To test the API, use:

* Swagger UI: `/docs`
* ReDoc: `/redoc`

Add tests under a `/tests` directory and run using `pytest` (if configured).

---

## 🤝 Contributing

We welcome contributions! Follow these steps:

1. Fork the repository
2. Create a new feature branch
3. Commit your changes
4. Submit a Pull Request

For bug reports or feature requests, feel free to open an issue.

---

## 🗂 Project Structure

```
App/
├── Models/                # Database models
│   ├── Classes/           # Business logic
│   └── db/                # DB schemas
├── route/                 # API endpoints
│   └── adminManagement/   # Admin-related routes
├── utils/                 # Helper functions
└── main.py                # Application entry point
```

---

## 🔑 Key Features

* ✅ Multi-tenant architecture
* 🔐 JWT-based authentication
* 👥 Role-based access control
* ⏱ Timesheet management
* 🏢 Tenant management
* 🧹 Modular and scalable codebase

---

## 📚 Resources

> For more tips on writing great READMEs, check out [this guide from Microsoft](https://docs.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops). You can also get inspired by these examples:
>
> * [ASP.NET Core](https://github.com/aspnet/Home)
> * [Visual Studio Code](https://github.com/Microsoft/vscode)
> * [Chakra Core](https://github.com/Microsoft/ChakraCore)
