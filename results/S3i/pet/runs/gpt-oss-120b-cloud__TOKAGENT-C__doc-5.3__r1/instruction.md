Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

The process of an Office Supply Request starts when any employee of the organization submits an office supply request. Once the requirement is registered, the request is received by the immediate supervisor of the employee requesting the office supplies. The supervisor must approve or ask for a change, or reject the request. If the request is rejected the process will end. If the request is asked to make a change then it is returned to the petitioner / employee who can review the comments for the change request. If the request is approved it will go to the purchase department that will be in charge of making quotations (using a subprocess) and select a vendor. If the vendor is not valid in the system the purchase department will have to choose a different vendor. After a vendor is selected and confirmed, the system will generate and send a purchase order and wait for the product to be delivered and the invoice received. In any case the system will send a notification to let the user know what the result was. In any of the cases, approval, rejection or change required the system will send the user a notification.
