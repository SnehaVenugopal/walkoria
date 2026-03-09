# Walkoria – Women's Shoe E-Commerce Platform

Walkoria is a full-stack e-commerce web application developed using **Django** that allows users to browse and purchase branded women's shoes online.
The platform provides features such as OTP-based authentication, product browsing, cart and checkout system, wallet payments, coupons, referral rewards, and a powerful admin dashboard for managing products, orders, and sales.

The project is containerized using **Docker** and deployed on **AWS EC2** with **Nginx** acting as a reverse proxy and **Gunicorn** serving the Django application.

---

# Live Demo

https://snehavg.site

---

# Features

## User Features

* User signup with **OTP verification**
* Secure login and authentication
* Browse products by category and brand
* Product filtering and search
* Add products to cart
* Checkout and place orders
* Order history and order detail page
* Wallet system for payments
* Coupon discounts
* Referral reward system

---

# Payment System

Walkoria supports multiple payment methods.

## Cash on Delivery (COD)

Users can place orders and pay when the product is delivered.

## Online Payment

Online payments are integrated using **Razorpay**, allowing users to pay securely using:

* UPI
* Debit cards
* Credit cards
* Net banking

## Wallet Payment

Users can also pay using their **internal wallet balance**.

---

# Order Management

## User Side

Users can:

* Place orders
* Track order status
* View order history
* Access **order details page** in their profile
* Cancel orders if applicable

---

## Admin Side

Administrators can:

* View all orders
* Update order status
* Manage order details
* Track revenue and sales performance

---

# Admin Dashboard

The Walkoria admin dashboard provides real-time analytics and management tools.

Features include:

* Total revenue overview
* Total orders
* Total users
* New users statistics
* Pending orders tracking
* Product management
* Category management
* Brand management
* Coupon and offer management
* Wallet management
* Sales reports
* Top products
* Top categories
* Top brands
* Recent orders monitoring

---

# Tech Stack

## Backend

* Python
* Django

## Database

* MySQL

## Frontend

* HTML
* CSS
* Bootstrap
* JavaScript

## Infrastructure

* Docker
* Nginx
* Gunicorn
* AWS EC2

---

# Project Modules

The application follows a modular Django architecture.

* **users** – Authentication and user management
* **product** – Product listing and details
* **category** – Product categories
* **brand** – Brand management
* **cart** – Shopping cart functionality
* **orders** – Order processing and management
* **wallet** – Wallet system and transactions
* **coupon** – Coupon discount system
* **referral** – Referral reward system
* **reviews** – Product rating and review system
* **userpanel** – User dashboard and order history
* **homepage** – Home page product listing
* **admin** – Admin dashboard and management tools
* **utils** – Helper functions and shared utilities

---

# Project Structure

walkoria/
│
├── admin/
├── brand/
├── cart/
├── category/
├── coupon/
├── homepage/
├── orders/
├── product/
├── referral/
├── reviews/
├── userpanel/
├── users/
├── wallet/
│
├── static/
├── templates/
├── utils/
│
├── walkoria/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
└── walkoria.sql

---

# Installation

## Clone the repository

git clone https://github.com/SnehaVenugopal/walkoria.git

## Navigate to project folder

cd walkoria

## Create virtual environment

python -m venv venv

## Activate virtual environment

Windows

venv\Scripts\activate

Linux / Mac

source venv/bin/activate

## Install dependencies

pip install -r requirements.txt

## Run migrations

python manage.py migrate

## Start development server

python manage.py runserver

Application will run at:

http://127.0.0.1:8000/

---

# Deployment Architecture

User Request
↓
Nginx (Reverse Proxy)
↓
Gunicorn (WSGI Server)
↓
Django Application
↓
MySQL Database

---

# Deployment Stack

Docker – Containerization
AWS EC2 – Cloud Hosting
Nginx – Reverse Proxy
Gunicorn – WSGI Application Server

---

# Future Improvements

* Product recommendation system
* Advanced analytics dashboard
* Mobile UI improvements
* AI-based product suggestions

---

# Author

Sneha Venugopal

GitHub
https://github.com/SnehaVenugopal
