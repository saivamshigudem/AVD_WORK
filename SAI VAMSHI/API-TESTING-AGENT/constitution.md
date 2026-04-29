ACMS Constitution (Agent Commission Management System)
Core Principles
I. API-First Design
All system features must be exposed via RESTful APIs compliant with OpenAPI 3.0. These APIs are the primary contracts guiding development. Data models must use JSON Schema with governance metadata (x-owner, x-version, x-description). APIs follow semantic versioning—with backward compatibility ensured unless a major version change is justified and documented.

II. Specification-Driven Development
The OpenAPI specification is the single source of truth. All code generation, implementation, and testing must follow the approved specs. Changes in business logic or data model require prior spec updates. Spec-It agents verify code aligns with the spec.

III. Test-First Automation
Automated test cases are mandatory, generated from specs before implementation. Tests cover happy path, edge cases, and error handling. Manual testing is supplemental only.

IV. Metadata-Driven Governance
All schemas and APIs must embed governance metadata: x-owner, x-version, x-description for traceability. Changes require Data Architect and Solution Architect approval.

V. Observability and Monitoring
Implement structured logging with correlation IDs. Monitor response times (<200ms target), throughput (≥10K req/min), and authentication failures or traffic anomalies. Use single MeterRegistryCustomizer bean only.

VI. Simplicity and Pragmatism
Avoid over-engineering. Use proven frameworks and libraries per stack. Generate clean, maintainable code stubs. Follow YAGNI—implement only what is specified. No duplicate configuration beans.

Technology Stack & Standards
Backend Implementation
Framework: Java Spring Boot 3.1.3

Java Version: 17 (LTS)

Maven Version: 3.8.8

Database: H2 in-memory database (default, for development and testing)

ORM: Spring Data JPA (Hibernate 6)

Logging: SLF4J + Logback

Exception Handling: Global @ControllerAdvice with consistent JSON error responses

Caching: Spring Cache abstraction with Caffeine 3.1.8 integration

API Documentation: Springdoc OpenAPI 1.6.14

Dependency Management (pom.xml essentials)
Java version set explicitly (version 17)

Spring Boot 3.1.3 starters for web, data-jpa, cache, actuator, and testing

H2 database included as runtime dependency

Jakarta EE 10 dependencies (jakarta.persistence, jakarta.validation, jakarta.annotation-api 2.1.1)

Caffeine 3.1.8 explicitly declared

Lombok for boilerplate reduction

Testing libraries: JUnit 5, Mockito, Spring Boot Test

CRITICAL: Exclude javax.annotation from spring-boot-starter-web to prevent javax/jakarta conflicts

Package and Imports
Root package: com.acms

Subpackages: controller, dto, service, repository, config, model

MANDATORY: Use Jakarta EE 10 namespaces only: jakarta.persistence.*, jakarta.validation.*, jakarta.annotation.*

PROHIBITED: javax.* imports cause compilation errors

Controllers expose plural noun endpoints with clear routing

DTOs define API contracts with validation annotations like @Valid, @NotNull

Directory and import structure explicitly defined for seamless compilation

Database Configuration
Use H2 in-memory database exclusively to avoid external database or driver errors.

Configure in application.yml as:

text
spring:
  datasource:
    url: jdbc:h2:mem:acmsdb;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE
    driver-class-name: org.h2.Driver
    username: sa
    password: ''
  jpa:
    hibernate:
      ddl-auto: update
    database-platform: org.hibernate.dialect.H2Dialect
    show-sql: true
  h2:
    console:
      enabled: true
      path: /h2-console
  cache:
    type: caffeine
    caffeine:
      spec: maximumSize=500,expireAfterWrite=600s
server:
  port: 8080
This setup enables an in-memory database with schema auto-creation and console access at /h2-console.

Caching
Cache read-heavy APIs using Spring Cache + Caffeine 3.1.8 integration with sensible TTL and size limits.

Single CacheConfig class only with named caches: "agents", "policies", "commissions".

NO CacheHealthIndicator - causes load exceptions.

Development Workflow & Quality Gates
Specification Phase
Business Analyst updates BRD.

Spec Agent generates OpenAPI 3.0 spec.

API Designer reviews and refines.

Solution Architect approves and locks spec.

Semantic versioning applied.

Code Generation Phase
CodeGen Agent generates Spring Boot stubs with correct dependencies and package structure.

MANDATORY: Replace all javax.* → jakarta.* imports automatically.

Backend Engineer completes logic using Lombok @RequiredArgsConstructor and Jakarta imports.

Code review ensures spec compliance and clear routing.

Testing Phase
Test Agent generates Python pytest suites from spec.

QA validates minimum 80% coverage with passing tests.

mvn clean verify must pass before merge.

Deployment Phase
DevOps manages Maven 3.8.8-based CI/CD pipeline on Java 17.

Automated tests run in pipeline.

Smoke tests verify endpoint availability without authentication issues.

Monitoring and logging configured.

Change Management
BRD changes approved by Product Owner and Sponsor.

API changes approved by API Designer and Solution Architect.

Metadata changes approved by Data Architect and Solution Architect.

Traceability via JIRA and decision records mandatory.

Governance & Documentation
Amendment Procedure
Document proposed amendment with rationale.

Review by Solution Architect and Spec-It Champion.

Assess impact on specs, code, tests.

Approval by Technical Steering Committee.

Semantic version updated accordingly.

Update dependent templates and configurations.

Versioning Policy
MAJOR: Breaking changes to APIs or principles.

MINOR: Addition of features or sections.

PATCH: Clarifications, wording improvements only.

Compliance Review
Quarterly reviews on constitutional adherence.

PRs must verify alignment with core principles before merge.

Spec-It agent configurations validated against constitution.

Code must pass: mvn clean compile with zero compilation errors.

Traceability & Audit
All requirements traceable: BRD → Spec → Implementation → Tests.

Changes tracked via JIRA.

Audit trails maintained through governance metadata.

Documentation Standards
Use clear, concise English, avoiding buzzwords.

Provide realistic OpenAPI 3.0 examples aligned with specs.

Maintain consistency across specification and plan files.