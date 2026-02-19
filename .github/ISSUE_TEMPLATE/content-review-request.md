---
name: Content Review Request
about: Used to request a content review
title: Content Review Request - [INSULT ID]
labels: content review request
assignees: Terry-BrooksJr

---

name: Report an Insult
title: Report API Insult
description: >-
  This form is used to request a content review for one of the following
  actions:
  	•	Reclassification of an explicit determination
  	•	Recategorization into a different or new insult category
  	•	Complete removal from the API
body:
  - type: input
    id: input-0
    attributes:
      value: "0000"
      label: Insult ID
      description: This UUID identifies the specific content being reviewed. The
        insult_id is included in the payload of every endpoint response
        throughout the API.
      placeholder: 4-Digit Insult ID
  - type: dropdown
    id: dropdown-1
    attributes:
      label: Type of Review
      description: This indicates the submitter’s intended purpose for the review.
        Available options include Reclassification, Recategorization, or
        Removal. If the purpose is unclear, select ‘General Review’.”
      options:
        - Reclassification
        - Recategorization
        - Removal
        - General Reveiw
      default: 0
  - type: checkboxes
    id: checkboxes-2
    attributes:
      label: "Post-Review Followup? "
      description: Do you want the reviewer to reach out to you following the review
        process?
      options:
        - Yes - I want to know the outcome
        - No - I do not need to know the outcome
  - type: input
    id: input-3
    attributes:
      label: Contact Information (Optional)
      description: This is required if you responded 'Yes' to the Post-Review
        Follow-up question. Please provide and email address or Github username.
      placeholder: "@Terry-Brooksjr  or API@yo-momma.net"
  - type: textarea
    id: textarea-4
    attributes:
      label: Basis for Requesting Review
      description: Please provide any information, comments, or context you believe
        justifies or supports a review of this content.
  - type: input
    id: input-5
    attributes:
      label: "New Category "
      description: If the Review Type is ‘Recategorization’, what do you believe the
        appropriate category should be?
