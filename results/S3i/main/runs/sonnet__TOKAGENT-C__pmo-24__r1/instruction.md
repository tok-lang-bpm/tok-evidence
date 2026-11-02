Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

A guest enters the restaurant when feeling hungry. 
He chooses a dish from the changing meal range and waits until it is his turn. 
Following this he places his order with the employee. The employee enters the order into the POS system and collects the money from the guest. 
After the payment, the employee sets up a buzzer and passes it on to the guest with the following information: 
"When the buzzer rings, your dinner is ready". 
Afterwards the employee informs the chef of the new meal order. 
The chef prepares the meal and places it in the service hatch. 
He then informs the employee that he has placed the finished meal in the service hatch. 
As soon as the employee is aware that the meal is ready he sets off the guest's buzzer. 
This is how the guest finds out that his meal is ready for collection. 
He can pick up his meal and eat it. 
As soon as the guest appears at the service hatch, the employee hands over his meal. 
Should a guest not react to the buzzer, the employee calls for him after 5 minutes, if necessary several times in a row.
