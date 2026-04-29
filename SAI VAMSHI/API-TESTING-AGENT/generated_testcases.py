import pytest
import requests
import json

# Base URL
base_url = "http://localhost:8080/api/api/v1"

# Actuator Base URL
actuator_base_url = "http://localhost:8080/api"

# Agent data
agent_data = {
    "agentCode": "AG1001",
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "phone": "1234567890",
    "status": "ACTIVE",
    "hireDate": "2026-01-01"
}

# Policy data
policy_data = {
    "policyNumber": "POL-2026-001",
    "policyType": "Auto",
    "status": "ACTIVE",
    "agentId": 1,
    "effectiveDate": "2026-01-01",
    "expirationDate": "2026-12-31",
    "premium": 1000.00,
    "coverageAmount": 50000.00
}

# Commission data
commission_data = {
    "policyId": 1,
    "agentId": 1,
    "commissionRate": 0.15,
    "premiumAmount": 1000.00,
    "commissionAmount": 150.00,
    "commissionType": "PERCENTAGE",
    "calculationDate": "2026-01-15",
    "effectiveDate": "2026-01-01",
    "expiryDate": "2026-12-31",
    "status": "PAID"
}

# Payment data
payment_data = {
    "commissionId": 1,
    "agentId": 1,
    "paymentAmount": 150.00,
    "paymentMethod": "BANK_TRANSFER",
    "status": "COMPLETED",
    "paymentDate": "2026-01-20",
    "bankAccount": "1234567890",
    "bankName": "National Bank",
    "transactionId": "TXN-2026-001",
    "notes": "Q1 2026 commission payment"
}

def create_agent():
    response = requests.post(f"{base_url}/agents", json=agent_data)
    assert response.status_code == 201

def create_policy():
    response = requests.post(f"{base_url}/policies", json=policy_data)
    assert response.status_code == 201

def create_commission():
    response = requests.post(f"{base_url}/commissions", json=commission_data)
    assert response.status_code == 201

def create_payment():
    response = requests.post(f"{base_url}/payments", json=payment_data)
    assert response.status_code == 201

def test_create_agent():
    create_agent()

def test_create_policy():
    create_policy()

def test_create_commission():
    create_commission()

def test_approve_commission():
    response = requests.patch(f"{base_url}/commissions/1/status?status=APPROVED")
    assert response.status_code == 200

def test_pay_commission():
    response = requests.patch(f"{base_url}/commissions/1/status?status=PAID")
    assert response.status_code == 200

def test_create_payment():
    create_payment()

def test_get_agents():
    response = requests.get(f"{base_url}/agents")
    assert response.status_code == 200

def test_get_policies():
    response = requests.get(f"{base_url}/policies")
    assert response.status_code == 200

def test_get_commissions():
    response = requests.get(f"{base_url}/commissions")
    assert response.status_code == 200

def test_get_payments():
    response = requests.get(f"{base_url}/payments")
    assert response.status_code == 200

def test_update_agent():
    response = requests.put(f"{base_url}/agents/1", json=agent_data)
    assert response.status_code == 200

def test_update_policy():
    response = requests.put(f"{base_url}/policies/1", json=policy_data)
    assert response.status_code == 200

def test_update_commission():
    response = requests.put(f"{base_url}/commissions/1", json=commission_data)
    assert response.status_code == 200

def test_update_payment():
    response = requests.put(f"{base_url}/payments/1", json=payment_data)
    assert response.status_code == 200

def test_delete_agent():
    response = requests.delete(f"{base_url}/agents/1")
    assert response.status_code == 204

def test_delete_policy():
    response = requests.delete(f"{base_url}/policies/1")
    assert response.status_code == 204

def test_delete_commission():
    response = requests.delete(f"{base_url}/commissions/1")
    assert response.status_code == 204

def test_delete_payment():
    response = requests.delete(f"{base_url}/payments/1")
    assert response.status_code == 204

def test_actuator():
    response = requests.get(f"{actuator_base_url}/actuator")
    assert response.status_code == 200

def test_actuator_prometheus():
    response = requests.get(f"{actuator_base_url}/actuator/prometheus")
    assert response.status_code == 200

def test_actuator_metrics():
    response = requests.get(f"{actuator_base_url}/actuator/metrics")
    assert response.status_code == 200

def test_actuator_info():
    response = requests.get(f"{actuator_base_url}/actuator/info")
    assert response.status_code == 200

def test_actuator_health():
    response = requests.get(f"{actuator_base_url}/actuator/health")
    assert response.status_code == 200

def test_actuator_env():
    response = requests.get(f"{actuator_base_url}/actuator/env")
    assert response.status_code == 200

def test_actuator_caches():
    response = requests.get(f"{actuator_base_url}/actuator/caches")
    assert response.status_code == 200