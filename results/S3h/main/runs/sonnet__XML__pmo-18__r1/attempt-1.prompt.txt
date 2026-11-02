Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

A university enrollment system involves the following steps:
Prospective students submit an application online.
The admissions office reviews the application and supporting documents.
If documents are missing, the applicant is notified to provide the missing items.
Upon receiving all documents, the application is evaluated by the admissions committee.
Concurrently, the finance department processes any application fees or waivers.
If the application is accepted, an acceptance letter is sent.
Otherwise, a rejection letter is sent and the process ends.
After being accepted, the student must then confirm enrollment by a specified deadline; otherwise the application will be canceled.
If the student confirms, they receive orientation materials and the IT department sets up student accounts for email, online portals, and library access.
If the student is international, the international student office assists with visa processing.
The student obtains a student ID card and starts creating their study plan, which includes:
Meeting with an academic advisor.
Selecting courses.
Resolving any schedule conflicts.
The student begins attending classes.
Throughout each semester, the student may add or drop courses within the add/drop period.
At the end of the semester, grades are posted, and the student can review them online.
If the student has any grievances, they can file an appeal, which includes:
Submitting an appeal form.
Meeting with the appeals committee.
Awaiting a decision.
The process repeats each semester until the student graduates or withdraws.
