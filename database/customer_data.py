import logging
import json
from datetime import datetime
from typing import List, Dict, Optional

from database.connect_db import (
    get_db_connection,
    get_db_transaction,
    close_connection_pool,
    DatabaseError
)

logger = logging.getLogger(__name__)

# This file contains functions to manage customer data in the database.
# Functions include creating, retrieving, updating, and deleting customer records.

class CustomerDataError(Exception):
    """Base exception for customer data errors"""
    pass

async def init_customer_table() -> None:
    """Initialize the customer table in the database."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS customers (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        persona TEXT, 
        email VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    # Persona is a JSON string containing customer profile details 
    # to decide 
    try:
        async with get_db_connection() as conn:
            await conn.execute(create_table_query)
            logger.info("Customer table initialized successfully.")
    except DatabaseError as e:
        logger.error(f"Error initializing customer table: {e}")
        raise CustomerDataError("Failed to initialize customer table.")


async def add_customer(name: str, email: str, persona: Optional[Dict] = None) -> int:
    """Add a new customer to the database."""
    insert_query = """
    INSERT INTO customers (name, email, persona)
    VALUES ($1, $2, $3)
    RETURNING id;
    """
    try:
        # Convert persona dict to JSON string if provided
        persona_json = json.dumps(persona) if persona else None
        
        async with get_db_connection() as conn:
            customer_id = await conn.fetchval(insert_query, name, email, persona_json)
            logger.info(f"Customer added successfully with ID: {customer_id}")
            return customer_id
    except DatabaseError as e:
        logger.error(f"Error adding customer: {e}")
        raise CustomerDataError("Failed to add customer.")

async def get_customer(customer_id: int) -> Optional[Dict]:
    """Retrieve a customer by ID."""
    select_query = """
    SELECT id, name, email, persona, created_at
    FROM customers
    WHERE id = $1;
    """
    try:
        async with get_db_connection() as conn:
            customer = await conn.fetchrow(select_query, customer_id)
            if customer:
                customer_dict = dict(customer)
                # Parse persona JSON string back to dict if present
                if customer_dict.get('persona'):
                    customer_dict['persona'] = json.loads(customer_dict['persona'])
                return customer_dict
            else:
                return None
    except DatabaseError as e:
        logger.error(f"Error retrieving customer: {e}")
        raise CustomerDataError("Failed to retrieve customer.")
    
async def update_customer(customer_id: int, name: Optional[str] = None, email: Optional[str] = None, persona: Optional[Dict] = None) -> bool:
    """Update an existing customer's details."""
    update_fields = []
    params = []
    if name:
        update_fields.append("name = $"+str(len(params)+1))
        params.append(name)
    if email:
        update_fields.append("email = $"+str(len(params)+1))
        params.append(email)
    if persona:
        update_fields.append("persona = $"+str(len(params)+1))
        # Convert persona dict to JSON string
        params.append(json.dumps(persona))
    
    if not update_fields:
        raise CustomerDataError("No fields to update.")
    
    update_query = f"""
    UPDATE customers
    SET {', '.join(update_fields)}
    WHERE id = ${len(params)+1};
    """
    params.append(customer_id)
    
    try:
        async with get_db_connection() as conn:
            result = await conn.execute(update_query, *params)
            return result == "UPDATE 1"
    except DatabaseError as e:
        logger.error(f"Error updating customer: {e}")
        raise CustomerDataError("Failed to update customer.")
    
async def delete_customer(customer_id: int) -> bool:
    """Delete a customer from the database."""
    delete_query = """
    DELETE FROM customers
    WHERE id = $1;
    """
    try:
        async with get_db_connection() as conn:
            result = await conn.execute(delete_query, customer_id)
            return result == "DELETE 1"
    except DatabaseError as e:
        logger.error(f"Error deleting customer: {e}")
        raise CustomerDataError("Failed to delete customer.")



# Create 10 mock vietnamese customers in insurance cases for testing
async def create_mock_customers() -> None:
    """Create 11 mock Vietnamese customers with comprehensive insurance-relevant personas."""
    mock_customers = [
        {
            "name": "Nguyễn Văn A", 
            "email": "vana@example.com", 
            "persona": {
                "age": 30, 
                "gender": "male",
                "job": "Software Engineer",
                "income": "25000000 VND/month",
                "marital_status": "married",
                "dependents": 1,
                "health_status": "good",
                "existing_insurance": ["health insurance"],
                "interests": ["investment", "education savings"],
                "risk_tolerance": "moderate",
                "insurance_needs": ["life insurance", "education savings plan"]
            }
        },
        {
            "name": "Trần Thị B", 
            "email": "tranb@example.com", 
            "persona": {
                "age": 25, 
                "gender": "female",
                "job": "Marketing Manager",
                "income": "18000000 VND/month",
                "marital_status": "single",
                "dependents": 0,
                "health_status": "excellent",
                "existing_insurance": [],
                "interests": ["travel", "health protection"],
                "risk_tolerance": "moderate",
                "insurance_needs": ["health insurance", "accident protection"]
            }
        },
        {
            "name": "Lê Văn C", 
            "email": "vanc@example.com", 
            "persona": {
                "age": 28, 
                "gender": "male",
                "job": "Teacher",
                "income": "12000000 VND/month",
                "marital_status": "single",
                "dependents": 2,
                "health_status": "good",
                "existing_insurance": [],
                "interests": ["saving for parents", "retirement"],
                "risk_tolerance": "conservative",
                "insurance_needs": ["critical illness", "retirement savings"]
            }
        },
        {
            "name": "Phạm Thị D", 
            "email": "vand@example.com", 
            "persona": {
                "age": 32, 
                "gender": "female",
                "job": "Doctor",
                "income": "35000000 VND/month",
                "marital_status": "married",
                "dependents": 2,
                "health_status": "good",
                "existing_insurance": ["health insurance", "life insurance"],
                "interests": ["children education", "investment"],
                "risk_tolerance": "moderate",
                "insurance_needs": ["education savings plan", "investment-linked insurance"]
            }
        },
        {
            "name": "Hoàng Văn E", 
            "email": "vane@example.com", 
            "persona": {
                "age": 29, 
                "gender": "male",
                "job": "Business Owner",
                "income": "50000000 VND/month",
                "marital_status": "married",
                "dependents": 1,
                "health_status": "fair",
                "existing_insurance": ["health insurance"],
                "interests": ["wealth accumulation", "business protection"],
                "risk_tolerance": "aggressive",
                "insurance_needs": ["investment-linked insurance", "critical illness", "life insurance"]
            }
        },
        {
            "name": "Đỗ Thị F", 
            "email": "vanl@example.com", 
            "persona": {
                "age": 26, 
                "gender": "female",
                "job": "Nurse",
                "income": "10000000 VND/month",
                "marital_status": "single",
                "dependents": 1,
                "health_status": "good",
                "existing_insurance": [],
                "interests": ["saving for future", "family protection"],
                "risk_tolerance": "conservative",
                "insurance_needs": ["health insurance", "savings plan"]
            }
        },
        {
            "name": "Vũ Văn G", 
            "email": "vang@example.com", 
            "persona": {
                "age": 27, 
                "gender": "male",
                "job": "Bank Teller",
                "income": "15000000 VND/month",
                "marital_status": "engaged",
                "dependents": 0,
                "health_status": "excellent",
                "existing_insurance": ["life insurance"],
                "interests": ["wedding planning", "home buying"],
                "risk_tolerance": "moderate",
                "insurance_needs": ["savings plan", "accident protection"]
            }
        },
        {
            "name": "Bùi Thị H", 
            "email": "buih@example.com", 
            "persona": {
                "age": 31, 
                "gender": "female",
                "job": "Accountant",
                "income": "20000000 VND/month",
                "marital_status": "married",
                "dependents": 3,
                "health_status": "good",
                "existing_insurance": ["health insurance"],
                "interests": ["children education", "retirement planning"],
                "risk_tolerance": "conservative",
                "insurance_needs": ["education savings plan", "retirement savings", "life insurance"]
            }
        },
        {
            "name": "Đặng Văn I", 
            "email": "vani@example.com", 
            "persona": {
                "age": 33, 
                "gender": "male",
                "job": "Construction Manager",
                "income": "22000000 VND/month",
                "marital_status": "married",
                "dependents": 2,
                "health_status": "fair",
                "existing_insurance": ["accident insurance"],
                "interests": ["family protection", "critical illness coverage"],
                "risk_tolerance": "moderate",
                "insurance_needs": ["critical illness", "life insurance", "health insurance"]
            }
        },
        {
            "name": "Trịnh Thị K", 
            "email": "vank@example.com", 
            "persona": {
                "age": 34, 
                "gender": "female",
                "job": "HR Manager",
                "income": "28000000 VND/month",
                "marital_status": "divorced",
                "dependents": 1,
                "health_status": "good",
                "existing_insurance": ["health insurance"],
                "interests": ["child education", "financial independence"],
                "risk_tolerance": "moderate",
                "insurance_needs": ["education savings plan", "retirement savings", "investment-linked insurance"]
            }
        },
        {
            "name": "Trịnh Thị N", 
            "email": "tn@example.com", 
            "persona": {
                "age": 29, 
                "gender": "female",
                "job": "AI Engineer",
                "income": "40000000 VND/month",
                "marital_status": "single",
                "dependents": 0,
                "health_status": "excellent",
                "existing_insurance": [],
                "interests": ["investment", "tech innovation", "early retirement"],
                "risk_tolerance": "aggressive",
                "insurance_needs": ["investment-linked insurance", "health insurance", "retirement savings"]
            }
        },
    ]

    try: 
        for customer in mock_customers:
            await add_customer(customer["name"], customer["email"], customer["persona"])
    finally:
        await close_connection_pool()

async def main():
    """Main function to run when module is executed directly."""
    try:
        await init_customer_table()
        # await create_mock_customers()
    finally:
        # Properly close the connection pool before exiting
        await close_connection_pool()

    
if __name__ == "__main__":
    import asyncio
    asyncio.run(create_mock_customers())
