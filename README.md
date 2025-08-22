YouTube Analytics Dashboard

<p align="center">
<img src="https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square" />
<img src="https://img.shields.io/badge/Django-5.1-green.svg?style=flat-square" />
<img src="https://img.shields.io/badge/DRF-API-red.svg?style=flat-square" />
<img src="https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS-orange.svg?style=flat-square" />
<img src="https://img.shields.io/badge/Docker-ready-blue.svg?style=flat-square" />
</p>

The YouTube Analytics Dashboard project is designed for monitoring and analyzing YouTube channels, providing users with a convenient and visual representation of their channel's growth and audience engagement.

About the Project

This web service allows a user to connect their YouTube channel via Google OAuth and get key analytics data without manually collecting it from different sources.

Key Features:

    Channel Statistics: Views, likes, comments, and subscriber growth.

    Time Trends: Daily and cumulative data for channels and videos over a selected period.

    Audience Demographics: Analysis of audience data by age and gender.

    Detailed Views: Statistics on views by device type (PC, mobile, etc.) and subscription status (subscribers/non-subscribers).

Technologies

The project is built using the following technologies and tools:

Backend

    Python 3.11+

    Django 5.1

    Django REST Framework (DRF) for creating API interfaces.

    PostgreSQL as the primary database.

    Google OAuth 2.0 for secure login and channel access.

    Google YouTube API v3 and YouTube Analytics API v2 for data collection.

    requests, google-auth, and google-api-python-client libraries.

    Swagger for automated API documentation.

    Unit tests to ensure code quality.

Frontend

    HTML, CSS, JavaScript

    Chart.js for visualizing statistics with interactive charts.

    Django templates for rendering pages.

Infrastructure

    Docker and docker-compose for easy and fast project deployment.

    Redis for caching and background tasks.

Running the Project (Docker)

To run the project locally using Docker, follow these steps:

    Clone the repository:
    

    git clone <repository_URL>
    cd <project_folder>
    
    Create the .env file:
    Based on the .env.example file, create a .env file and fill it with the necessary data, including your Google OAuth keys.
    
    
    cp .env.example .env
    
    Run Docker Compose:
    Execute the following command in the project's root directory to build and start all services (web server, database, Redis).
    
    docker-compose up --build
    
    Apply migrations:
    After the containers are up and running, apply migrations to create the database tables.
    
    
    docker-compose exec web python manage.py migrate

Create a superuser:
To access the Django Admin, create a superuser account.


    docker-compose exec web python manage.py createsuperuser

    Done!
    The project will be available at http://localhost:8000.

API Documentation

The API documentation is available at http://localhost:8000/api/swagger/ after the project has been launched. 
