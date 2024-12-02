# Carrier Platform Status Report Generator
Board summary for engagements in Carrier.
This script generates a status report from a carrier platform and sends it via email. 
It interacts with the Carrier API to fetch tickets and audit logs, categorizes the tickets, and sends a summary report through email.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Logging](#logging)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Features

- Fetches tickets from the Carrier API.
- Categorizes tickets into different statuses.
- Fetches audit logs to identify recently completed tickets.
- Generates an HTML report using Jinja2 templates.
- Sends the report via email using SMTP.

## Requirements

- Python 3.7+
- `requests` library
- `jinja2` library
- `smtplib` library

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/board_summaryt.git
    cd board_summaryt
    ```

2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

### Running the Script Locally

To run the script locally, you can use the `handler_local` function. This function is intended for local debugging and testing.

```python
from script import handler_local

event = {
    "base_url": "https://api.example.com",
    "token": "your_token_here",
    "project_id": "your_project_id_here",
    "board_id": "your_board_id_here",
    "host": "smtp.example.com",
    "port": 465,
    "user": "your_user_here",
    "passwd": "your_password_here",
    "sender": "sender@example.com",
    "recipients": "recipient@example.com"
}

response = handler_local(event)
print(response)