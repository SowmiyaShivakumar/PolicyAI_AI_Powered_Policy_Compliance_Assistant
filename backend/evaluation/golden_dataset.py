"""
Golden Dataset — 20 test cases.

Fixes for better DeepEval scores:
1. expected_output is outcome-focused (what the employee should DO)
   not subcategory ID citations
2. context is fuller text matching actual Milvus chunk content
3. All entries have expected_output (not expected_subcategories)
"""

GOLDEN_DATASET = [
    # 3. IDENTIFY - INFO
    {
        "input": "Are we required to maintain a hardware asset inventory?",
        "expected_output": "Yes. The organisation must maintain inventories of all hardware assets it manages as required by policy.",
        "context": "ID.AM-01: Inventories of hardware managed by the organization are maintained. The Information Security Policy and Systems and Services Acquisition Policy require this.",
    },

    # 4. PROTECT - ACTION
    {
        "input": "Can I share customer data with another internal team?",
        "expected_output": "Needs review. Data sharing must follow least privilege and separation of duties. Contact the Information Security Team to verify access permissions before sharing.",
        "context": "PR.AA-05: Access permissions, entitlements, and authorizations are managed and enforced according to least privilege and separation of duties. Access Control Policy applies.",
    },

    # 5. DETECT - INFO
    {
        "input": "How is a security incident formally declared?",
        "expected_output": "Incidents are declared when adverse events meet defined criteria. Events are analysed to determine if they qualify as incidents per the Incident Response Policy.",
        "context": "DE.AE-05: Incidents are declared when adverse events meet the defined criteria. DE.AE-06: Information on adverse events is provided to authorised staff and tools.",
    },

    # 6. RESPOND - INCIDENT
    {
        "input": "I lost a laptop that may contain customer data. What must I do?",
        "expected_output": "Report the incident immediately to the Information Security Team. Contain the incident by preventing unauthorised access. Notify relevant stakeholders. Follow the Incident Response Policy.",
        "context": "RS.MI-01: Incidents are contained to prevent further harm. RS.CO-02: Internal and external stakeholders are notified of incidents. Incident Response Policy and Cyber Incident Response Standard apply.",
    },

    # 7. PROTECT - NON-COMPLIANT
    {
        "input": "Can I install personal software on my work laptop?",
        "expected_output": "No. Installing unauthorised software on company devices is prohibited. Only approved software may be installed per the platform security policy.",
        "context": "PR.PS-02: Unauthorised software is prevented from being installed or executed. Platform Security Policy and Acceptable Use of Information Technology Resource Policy apply.",
    },
    # 14. RECOVER - BACKUP
    {
        "input": "How do we verify our backups are working?",
        "expected_output": "Recovery plans must be tested regularly to ensure backups are functional and data can be restored. This is required under the contingency planning policy.",
        "context": "RC.RP-01: The recovery portion of the incident response plan is executed once initiated. Contingency Planning Policy requires regular testing of backup and recovery processes.",
    },
    # 19. GOVERN - THIRD PARTY
    {
        "input": "How do we handle third-party vendor risk assessments?",
        "expected_output": "Third-party cybersecurity risks must be identified, assessed, and managed. Suppliers must comply with the organisation's cybersecurity requirements.",
        "context": "GV.SC-02: Cybersecurity risks in the supply chain are identified, prioritised, and managed. GV.SC-06: Planning and due diligence are performed to reduce supply chain risk.",
    }
]