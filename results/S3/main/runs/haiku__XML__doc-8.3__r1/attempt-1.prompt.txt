Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

I am the Head of the functional department. When I have detected a number of personnel requirements, I report the vacancy to the Personnel Department. Then I wait to get the job description for review before it is advertized. Under certain circumstances, I must ask for corrections again, otherwise I approve the job description. Sometimes it also happens that the colleague from the HR department still has questions about the tasks and requirements before he can describe the job. Then I am available for clarifications, of course.
