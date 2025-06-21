#!/usr/bin/env python3
"""
Test script for InvoiceNinja integration
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.invoice_llm_processor import get_invoice_llm_processor
from app.invoice_ninja import InvoiceNinjaClient

async def test_invoice_integration():
    """Test the InvoiceNinja integration."""
    print("Testing InvoiceNinja Integration...")
    
    try:
        # Test basic client connection
        print("\n1. Testing InvoiceNinja client connection...")
        client = InvoiceNinjaClient()
        
        # Test getting clients
        print("\n2. Testing get clients...")
        clients = await client.get_clients()
        print(f"Found {len(clients)} clients")
        
        # Test getting invoices
        print("\n3. Testing get invoices...")
        invoices = await client.get_invoices(limit=5)
        print(f"Found {len(invoices)} invoices")
        
        # Test LLM processor
        print("\n4. Testing LLM processor...")
        processor = await get_invoice_llm_processor()
        
        # Test creating an invoice
        print("\n5. Testing invoice creation...")
        result = await processor.create_invoice(
            description="Test invoice from LLM integration",
            amount=99.99,
            client_name="Test Client",
            client_email="test@example.com"
        )
        
        if result["success"]:
            print(f"✅ Invoice created successfully: {result['message']}")
            print(f"Invoice ID: {result.get('invoice_id')}")
        else:
            print(f"❌ Failed to create invoice: {result['message']}")
        
        # Test getting invoices through LLM processor
        print("\n6. Testing get invoices through LLM processor...")
        invoices_result = await processor.get_invoices(limit=3)
        if invoices_result["success"]:
            print(f"✅ Retrieved {invoices_result['count']} invoices")
        else:
            print(f"❌ Failed to get invoices: {invoices_result['message']}")
        
        await client.close()
        await processor.close()
        
        print("\n🎉 All tests completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Wait for user to press Enter before closing
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    asyncio.run(test_invoice_integration()) 