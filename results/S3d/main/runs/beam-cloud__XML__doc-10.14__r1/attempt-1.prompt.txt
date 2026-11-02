Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

If the MPOO sends the bill for the temporary continuation of the metering point operations to the GO, the GO examines the bill. If the MSPO sends the bill for the temporary continuation of the measurement to the GO, the GO examines the bill. If the MSPO sends the bill for additional readings to the GO, the GO examines the bill. If the MPOO sends the bill for the equipment acquisition to the MPON or the GO, the MPON or the GO examines the bill. The GO or the MPON confirms the invoice with payment advice to the MPOO or the MSPO, or the GO or the MPON rejects the invoice of the MPOO or the MSPO.
