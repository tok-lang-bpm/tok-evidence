Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

I am the HR clerk. When a vacancy is reported to me, I create a job description from the information. Sometimes there is still confusion in the message, then I must ask the Department again. I am submitting the job description for consideration and waiting for the approval. But, it can also happen that the department does not approve it, but rejects it, and requests a correction. Then I correct the description and submit it again for consideration. If the description is finally approved, I post the job.
