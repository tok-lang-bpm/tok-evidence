Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Mail from the party is collected on a daily basis by the Mail Processing Unit. Within this unit, the Mail Clerk sorts the unopened mail into the various business areas. The mail is then distributed. When the mail is received by the Registry, it is opened and sorted into groups for distribution, and thus registered in a manual incoming Mail Register. Afterwards, the Assistant Registry Manager within the Registry performs a quality check. If the mail is not compliant, a list of requisition explaining the reason for rejection is compiled and sent back to the party. Otherwise, the matter details (types of action) are captured and provided to the Cashier, who takes the applicable fees attached to the mail. At this point, the Assistant Registry Manager puts the receipt and copied documents into an envelope and posts it to the party. Meantime, the Cashier captures the Party Details and prints the Physical Court File.
