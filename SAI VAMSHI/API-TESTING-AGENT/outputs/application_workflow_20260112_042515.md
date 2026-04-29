# Application Workflow

Here's the workflow of the application with a recommended API execution order:

1. **System Initialization**
	* The system starts and initializes the database, caching, and other components.
	* The API endpoints are registered and ready to receive requests.

2. **Actors Involved**
	* Insurance Administrators: manage agent records, policies, and commissions.
	* Managers: view agent performance summaries.
	* System: automatically calculates commissions and processes payments.

3. **Request Flow**
	* The client (e.g., web application, mobile app) sends a request to the API endpoint.
	* The request is received by the API gateway and routed to the corresponding controller.
	* The controller processes the request, performs validation, and calls the service layer.

4. **Core Processing Logic**
	* **Agent Management**:
		+ Create Agent: `POST /api/v1/agents`
		+ Get Agent: `GET /api/v1/agents/{id}`
		+ Update Agent: `PUT /api/v1/agents/{id}`
		+ Deactivate Agent: `PATCH /api/v1/agents/{id}/status`
	* **Policy Management**:
		+ Create Policy: `POST /api/v1/policies`
		+ Get Policy: `GET /api/v1/policies/{id}`
		+ Update Policy: `PUT /api/v1/policies/{id}`
		+ Get Policies by Agent: `GET /api/v1/policies/agent/{agentId}`
	* **Commission Calculation**:
		+ Calculate Commission: `POST /api/v1/commissions/calculate`
		+ Get Commission: `GET /api/v1/commissions/{id}`
	* **Payment Processing**:
		+ Create Payment: `POST /api/v1/payments`
		+ Get Payment: `GET /api/v1/payments/{id}`
		+ Update Payment Status: `PATCH /api/v1/payments/{id}/status`

5. **Validation & Governance**
	* Input validation: validate request data using JSON Schema and Jakarta Validation.
	* Governance metadata: embed metadata (x-owner, x-version, x-description) in API responses.

6. **Error Handling**
	* Error responses: return consistent error format with error code, message, and details.
	* Error handling: handle errors using Global @ControllerAdvice and return error responses.

7. **Final Response Flow**
	* The service layer returns the response to the controller.
	* The controller returns the response to the API gateway.
	* The API gateway returns the response to the client.

8. **API Execution Order**
	* Create Agent: `POST /api/v1/agents`
	* Create Policy: `POST /api/v1/policies`
	* Calculate Commission: `POST /api/v1/commissions/calculate`
	* Create Payment: `POST /api/v1/payments`
	* Get Agent: `GET /api/v1/agents/{id}`
	* Get Policy: `GET /api/v1/policies/{id}`
	* Get Commission: `GET /api/v1/commissions/{id}`
	* Get Payment: `GET /api/v1/payments/{id}`
	* Update Agent: `PUT /api/v1/agents/{id}`
	* Update Policy: `PUT /api/v1/policies/{id}`
	* Update Payment Status: `PATCH /api/v1/payments/{id}/status`

Note: The API execution order is not strictly sequential, as some APIs can be executed concurrently or in parallel. However, the above order provides a general guideline for the workflow of the application.