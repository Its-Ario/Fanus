# Fanus: Product Overview

## What Fanus is

Fanus is an offline-first desktop application for managing students and supporting their academic progress in a school. It is designed for school counselors and staff who need a practical way to keep student records, review attendance and grades, organize weekly study plans, and notice students who may need attention.

Fanus keeps its working data on the local computer. It is intended to run as a standalone Windows application and remain useful without an internet connection. Its interface is designed for Persian-speaking schools: it supports right-to-left layouts, Persian text and digits, and the Persian school week and calendar conventions where relevant.

Fanus is a school support and organization tool. It helps staff collect information and make plans; it does not replace a counselor's judgment, a teacher's assessment, or direct communication with a student and family.

## Who uses it

- **Counselors** maintain student records, review academic and attendance history, create study plans, and keep private counseling notes.
- **School administrators** organize school and classroom information, manage user accounts and permissions, and review school-wide information where available.
- **Other staff users** use the parts of the application their account is permitted to access, such as entering grades or attendance.

Available actions depend on the user's role and assigned permissions. Some management actions are restricted to users who can manage accounts and school settings; the confidential notes vault is intended for counselors.

## How a typical workflow fits together

1. The school is set up with its name, academic year, classes, users, and access rules.
2. Staff add students individually or, where the roster import feature is available, load a roster from a spreadsheet after reviewing the proposed changes.
3. Staff maintain student records by entering attendance and exam results.
4. A counselor reviews a student's academic context and creates or adjusts a weekly study plan.
5. The counselor reviews the proposed schedule, makes changes where needed, and assigns an appropriate plan to the student.
6. Staff use the dashboard, student records, and school-wide summaries to follow progress and identify items that need attention.
7. The school can create a backup and restore it later when moving or recovering local data.

The exact availability of each step depends on the current application build and whether the school has entered the relevant data.

## Main features

### Dashboard

The dashboard gives staff a quick view of school activity and student progress. It is meant to answer questions such as how many students are being tracked, which plans are active, how much planned work is being completed, and which students may need follow-up. It brings important indicators and attention items together so staff can decide where to look next.

Dashboard indicators depend on the underlying records. A missing attendance history, grade history, or student check-in history can make a summary incomplete or leave it without enough data to show a trend.

### Student directory

The student directory is the main place to find and maintain student records. Staff can browse and search the roster and use class-related filters to narrow the list. A student record connects the student's identity and classroom with relevant academic, attendance, and planning information.

Student records help staff move from a school-wide view to one student's situation. Creating or updating a student's record does not itself create a study plan or determine a student's needs; those are separate staff workflows.

### Student profile

The student profile gathers an individual student's information in one place. Depending on the data available, it can present a summary and history, the student's weekly study plan, and confidential counselor notes.

The profile is intended to help a counselor understand context before acting. Academic and attendance histories are based on records entered into Fanus. Private notes are handled separately from ordinary school records and are only available through the counselor vault workflow.

### Study planning

Study planning turns a student's goals and academic context into a weekly schedule of study sessions. The counselor can start or regenerate a plan, inspect its scheduled blocks, make manual changes, and lock sessions that should remain fixed. A plan can then be approved and assigned to the student.

Plan generation uses information such as the student's target or exam, subject priorities, academic weaknesses where grade data is available, and available time. It attempts to place study sessions into the student's week while respecting scheduling limits. The planner can try less demanding arrangements when the first schedule does not fit. If it cannot place every requested session, the counselor may see a warning about the remaining workload.

Generated plans are drafts for human review. The counselor remains responsible for adjusting workload and deciding whether the plan is appropriate. A plan's completion information reflects recorded check-ins or other available progress data; it should not be treated as proof of learning or mastery.

### Exams and grade entry

Staff can organize exam results by exam, class, and subject. An exam provides shared context such as its name, date, term, participating classes, subjects, and score ceiling. Scores are entered for students in a grid, allowing staff to move through a class and its subjects efficiently.

Grade records provide an academic history for each student. Fanus can use eligible grade records to summarize performance, calculate an average, and identify comparatively weak subjects for study planning. The meaning of an average depends on the configured term rules and the scores entered. Missing or exempt results are distinct from a score of zero.

Grade trends are only as reliable as the data entered. A score describes recorded exam performance; it is not a complete measure of a student's ability or circumstances.

### Attendance

Attendance entry lets staff record a student's attendance status for a school day and, where applicable, a reason. These records can be reviewed as part of the student's history and may contribute to broader summaries.

Attendance records are useful for spotting patterns and prompting follow-up. They do not explain the cause of an absence by themselves. Any interpretation should account for the reason and the school's own attendance practices.

### School analytics

The analytics area is intended to summarize patterns across students, classes, and subjects. Designed views include the distribution of recorded risk levels, study-plan completion over recent weeks, attendance in relation to academic performance, and planned study workload by subject. Grade and major filters help staff focus on a group.

These summaries are descriptive signals for school staff, not diagnoses or decisions about a particular student. Some views can be empty or limited when the school has not yet collected the necessary attendance, grade, or plan-progress data. Risk summaries reflect the risk information currently recorded for students; they should not be assumed to be an independently verified assessment.

### School, class, and user settings

Settings let authorized users maintain school information, class structure, and user accounts. Users can change their own account password. Counselors can manage the confidential vault PIN. Administrative changes can be recorded in an audit history so authorized staff can review who made important changes.

Permissions shape which information a user can view or change. Settings are intended to keep school structure and account access consistent with the school's responsibilities.

### Confidential counselor notes

Counselor notes are private notes associated with a student for counseling context. They are stored in a separate, protected local vault rather than alongside the ordinary student record. A counselor opens the vault using its PIN when private notes are needed; the vault can otherwise remain locked.

The separation is intended to reduce casual access to sensitive counseling information. Schools should still protect the computer and its local data, choose an appropriate PIN, and follow their own privacy and record-keeping policies.

### Student roster import and export

Roster file workflows help staff move basic student directory information into or out of Fanus. An import can be previewed before it is committed, allowing staff to inspect rows that would be added, skipped as duplicates, or rejected for missing or invalid information. Import is intended for adding students, not silently updating existing records. Export is useful for producing a portable roster view for school administration.

Roster files cover basic identity and class information. They are not a complete export of grades, attendance, study plans, or confidential notes.

### Backup and restore

Fanus can create a portable backup of school data and restore it later. A backup can include ordinary school records; a counselor may also include the private vault when it is unlocked and the counselor chooses to include it. Restoring replaces the current data with the data from the selected backup, so it is a recovery or migration action rather than a merge.

Backups help protect against computer loss or data damage. A backup that includes the counselor vault also carries sensitive information and should be stored accordingly. Access to a backup file should be treated as access to school records.

### Printable reports

Fanus includes printable PDF outputs for study plans and academic summaries. These give staff a way to share or keep a paper copy of relevant student information. Confidential counselor notes are not intended to appear in ordinary school reports.

## Principles behind the product

- **Works offline:** normal school workflows should not depend on an internet connection or a cloud account.
- **Local ownership:** the school's working records live with the local installation and its backups.
- **Human review:** generated schedules and summary indicators support staff judgment; they do not make final counseling or academic decisions.
- **Privacy boundaries:** confidential counselor notes have a separate access and storage path from routine school records.
- **Persian-first usability:** the interface is built for Persian text, right-to-left reading, and local school conventions.
- **Practical on modest computers:** the app aims to remain usable on older or lower-powered Windows hardware.

## Important limits when interpreting Fanus data

- Fanus can only summarize information that staff have entered or that the application has recorded.
- A blank chart or absent history may mean there is not enough data, rather than that there is no issue.
- A risk label, grade average, attendance count, or plan completion rate is a limited indicator, not a full account of a student.
- A generated study plan is a proposal for counselor review and adjustment.
- Fanus is designed for local school use; LAN sharing and automatic multi-computer synchronization are not part of the standalone product described here.
- Availability and behavior can vary by release. Product designs and plans are not proof that a feature is present in every installed build.

## Guidance for an AI assistant reading this overview

Treat Fanus as an offline-first, Persian-oriented school student-management and academic-support application. Its central purpose is to help school staff organize student records, enter academic and attendance information, and support counselors in making and reviewing weekly study plans.

When discussing a feature, distinguish these three things:

1. **Recorded information:** facts entered by school staff, such as a score or attendance entry.
2. **Computed summaries or proposals:** averages, trends, risk indicators, or generated schedules derived from available records.
3. **Professional judgment:** a counselor's or educator's interpretation and decision about what a student needs.

Do not describe Fanus as a cloud service, a student-facing social network, an autonomous counselor, or a replacement for school staff. Do not assume that a designed or planned feature is available in every release, or that missing data means a student has no needs.
