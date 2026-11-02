Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: Find a Job

You have to regularly report, to which companies you wrote job applications.
Based on your job applications, new potential job offers are sent to you.
Companies have to confirm that they received job applications and rate the application.
A job interview can be negotiated.
When a company wants you to work for them, you enter the probation phase.
After probation phase, you can rate the company and the company can rate you.
Reviews for a company can only be seen (by job applicants) after 1 year.
If a job becomes permanent, the process ends, unless you rated the company C or less, then you continue to receive job offers, but no longer have to report.
