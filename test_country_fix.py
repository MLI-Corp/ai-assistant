#!/usr/bin/env python3
"""
Test script to verify the country_id fix
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.invoice_ninja import InvoiceNinjaClient

async def test_country_fix():
    """Test the country_id fix."""
    print("Testing Country ID Fix...")
    
    try:
        client = InvoiceNinjaClient()
        
        # Test getting countries
        print("\n1. Testing get countries...")
        countries = await client.get_countries()
        print(f"Found {len(countries)} countries")
        if countries:
            print(f"First country: {countries[0]['name']} (ID: {countries[0]['id']})")
        
        # Test creating a client with valid country
        print("\n2. Testing client creation with valid country...")
        client_data = {
            'name': 'Test Client Fix',
            'email': 'testfix@example.com',
            'phone': '',
            'address1': '',
            'address2': '',
            'city': '',
            'state': '',
            'postal_code': ''
        }
        
        result = await client.create_client_with_valid_country(client_data)
        print(f"✅ Client created successfully: {result['data']['name']}")
        
        await client.close()
        print("\n🎉 Country fix test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Wait for user to press Enter before closing
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    asyncio.run(test_country_fix()) 