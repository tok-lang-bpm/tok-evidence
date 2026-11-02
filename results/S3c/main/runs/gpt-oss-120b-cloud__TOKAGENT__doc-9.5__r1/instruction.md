Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

After the Expense Report is received, a new account must be created if the employee does not already have one. The report is then reviewed for automatic approval. Amounts under $200 are automatically approved, whereas amounts equal to or over $200 require approval of the supervisor. In case of rejection, the employee must receive a rejection notice by email. Otherwise, the reimbursement goes to the employees direct deposit bank account. If the request is not completed in 7 days, then the employee must receive an approval in progress email. If the request is not finished within 30 days, then the process is stopped and the employee receives an email cancellation notice and must re-submit the expense report.
