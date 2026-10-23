
# Porchlight - Testing and Evaluation

## Overview

I tested the Porchlight backend locally to check that the existing functionality was working before the final demo. I focused on running the automated tests and checking one of the demo scenarios.

## 1. Backend Testing

I ran the existing tests using pytest.

| Result | Count |
|--------|-------|
| Passed | 17 |
| Failed | 0 |
| Total | 17 |

All 17 tests passed after I fixed two time-formatting issues that were causing errors on Windows.

The original code used `%-I` to format the time, which wasn't supported in my Windows environment. I changed the formatting locally and reran the tests.

## 2. Demo Testing

I started the backend locally with the AI agent disabled and tested the package delivery scenario.

The API accepted the request and returned:

- Started: True
- Scenario: package

I then checked the `/api/events` endpoint to see whether any events had been generated.

The endpoint returned an empty result, so I couldn't confirm whether the package scenario produced an alert.

## 3. Limitations

Testing was carried out locally without a live Ring connection or AWS Bedrock.

I haven't measured the vision model's accuracy or tested the real AI agent's decisions, so those results aren't included here.

## 4. Conclusion

The backend passed all 17 existing automated tests, which was a good starting point for checking the project before submission.

The package demo also started successfully, although I couldn't verify the alert output from the events endpoint.

Further testing would be needed to confirm how the complete system performs with live inputs and the AI agent enabled.

