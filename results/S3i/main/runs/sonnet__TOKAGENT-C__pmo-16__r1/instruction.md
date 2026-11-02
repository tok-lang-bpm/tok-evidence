Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

In a multinational company's annual audit process, the audit coordinator initiates the audit process by sending a notification to the regional office.
The regional office prepares financial statements and gathers necessary documents.
Concurrently, the compliance team checks for any regulatory updates that might affect the audit.
Afterward, the regional office submits the documents to the central audit team.
The central audit team reviews the submission.
If discrepancies are found, they request clarifications from the regional office.
The regional office provides the necessary clarifications.
Once all documents are reviewed without issues, the audit team conducts a risk assessment.
The risk assessment includes evaluating financial risks, operational risks, and compliance risks, which can be done in any order but must all be completed.
If high risk is identified, then a detailed investigation is launched.
The investigation includes data analysis, interviews, and, in certain cases, site visits.
After all risks are addressed, the audit team compiles the audit report.
The report is reviewed by the audit director.
The audit director may approve the report or send it back for revisions.
If revisions are required, the audit team updates the report accordingly and resubmits it to be reviewed again by the audit director.
Once approved, the final report is distributed to the executive board and archived.
The entire audit process is then closed.
