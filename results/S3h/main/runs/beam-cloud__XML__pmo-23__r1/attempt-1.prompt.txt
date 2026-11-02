Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

The sales clerks in a bank can use their software frontend to receive the credit-scoring for a certain customer. 
This starts a process in the banking system which communicates with the agency in the background. 
This process sends a scoring request to the agency right after the beginning. 
Then, the Agency does a first quick scoring (level 1). 
This will often lead to an immediate result which is then returned directly to the banking system within seconds. 
The banking process presents the result to the clerk sitting at the frontend. 
Sometimes the scoring cannot be determined immediately and takes longer. 
In this case the agency informs the banking process of the delay and then starts the level 2 scoring (which can take up to a couple of minutes). 
After the scoring result is determined, the information is sent back to the banking process. 
The banking process displays a message to the clerk when he receives information about the delay to check again later. 
As soon as the result arrives, it can be seen at the frontend.
