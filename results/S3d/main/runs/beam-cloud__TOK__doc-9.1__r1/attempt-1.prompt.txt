Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Every weekday morning, the database is backed up and then it is checked to see whether the Account Defaulter table has new records. If no new records are found, then the process should check the CRM system to see whether new returns have been filed. If new returns exist, then register all defaulting accounts and customers. If the defaulting client codes have not been previously advised, produce another table of defaulting accounts and send to account management. All of this must be completed by 2: 30 pm, if it is not, then an alert should be sent to the supervisor. Once the new defaulting account report has been completed, check the CRM system to see whether new returns have been filed. If new returns have been filed, reconcile with the existing account defaulters table. This must be completed by 4: 0 pm otherwise a supervisor should be sent a message.
