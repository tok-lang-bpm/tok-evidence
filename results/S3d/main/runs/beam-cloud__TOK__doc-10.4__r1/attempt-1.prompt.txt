Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

The MPON notifies the MPOO about equipment change intentions. The MPOO announces self dismounting to the MPON or the MPOO shall notify the MPON about no self-dismounting of the MPOO. The MPON or the MPOO perform the final reading. The MPON or the MPOO dismount the old equipment. The MPON mounts the new device. The MPON reads the meter count from the installed meter. The MPON sents the values of the final reading to the GO. The MPON tells the GO about the device changes, the master data and the meter count at installation. The GO shall notify the MSP about the device changes, the master data, the meter count at dismounting, and the meter count at installation.
