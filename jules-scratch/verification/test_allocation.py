import uuid
from playwright.sync_api import sync_playwright, expect
from datetime import date, timedelta
import re

def run_verification(playwright):
    # Generate unique names for this run
    unique_id = str(uuid.uuid4())[:8]
    organizer_user = f"organizer_{unique_id}"
    worker_a_user = f"worker_A_{unique_id}" # Works Mon, Wed, Fri
    worker_b_user = f"worker_B_{unique_id}" # Works Tue, Thu
    customer_name = f"Alloc_Customer_{unique_id}"
    password = "password123"

    # A Monday in the current week
    today = date.today()
    schedule_date = today - timedelta(days=today.weekday())

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    base_url = "http://127.0.0.1:5000"

    try:
        # Step 1: Register users
        print("Registering users...")
        # Organizer
        page.goto(f"{base_url}/register")
        page.get_by_label("Username").fill(organizer_user)
        page.get_by_label("Password").fill(password)
        page.get_by_label("Email").fill(f"organizer_{unique_id}@test.com")
        page.get_by_label("Role").select_option("organizer")
        page.get_by_role("button", name="Register").click()
        # Worker A
        page.goto(f"{base_url}/register")
        page.get_by_label("Username").fill(worker_a_user)
        page.get_by_label("Password").fill(password)
        page.get_by_label("Email").fill(f"worker_a_{unique_id}@test.com")
        page.get_by_label("Role").select_option("worker")
        page.get_by_role("button", name="Register").click()
        # Worker B
        page.goto(f"{base_url}/register")
        page.get_by_label("Username").fill(worker_b_user)
        page.get_by_label("Password").fill(password)
        page.get_by_label("Email").fill(f"worker_b_{unique_id}@test.com")
        page.get_by_label("Role").select_option("worker")
        page.get_by_role("button", name="Register").click()

        # Step 2: Login as Organizer and set up staff availability
        print("Logging in and setting up staff...")
        page.goto(f"{base_url}/login")
        page.get_by_label("Username").fill(organizer_user)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Login").click()

        page.get_by_role("link", name="Manage Staff").click()
        # Edit Worker A
        page.locator("li", has_text=worker_a_user).get_by_role("link", name="Edit Address").click()
        page.evaluate("document.querySelector('input[name=\"latitude\"]').value = '51.503364'")
        page.evaluate("document.querySelector('input[name=\"longitude\"]').value = '-0.127625'")
        page.get_by_label("Contracted Weekly Hours").fill("40")
        page.get_by_label("Mon").check()
        page.get_by_label("Wed").check()
        page.get_by_label("Fri").check()
        page.get_by_role("button", name="Update Details").click()
        expect(page.get_by_text(f"{worker_a_user}'s details updated!")).to_be_visible()
        # Edit Worker B
        page.locator("li", has_text=worker_b_user).get_by_role("link", name="Edit Address").click()
        page.evaluate("document.querySelector('input[name=\"latitude\"]').value = '52.2053'")
        page.evaluate("document.querySelector('input[name=\"longitude\"]').value = '0.1218'")
        page.get_by_label("Contracted Weekly Hours").fill("30")
        page.get_by_label("Tue").check()
        page.get_by_label("Thu").check()
        page.get_by_role("button", name="Update Details").click()
        expect(page.get_by_text(f"{worker_b_user}'s details updated!")).to_be_visible()

        # Step 3: Create a customer and a job for a Monday
        print("Creating customer and job...")
        page.get_by_role("link", name="Back to Dashboard").click()
        page.get_by_role("link", name="Manage Customers").click()
        page.get_by_role("link", name="Add New Customer").click()
        page.get_by_label("Name").fill(customer_name)
        page.evaluate("document.querySelector('input[name=\"latitude\"]').value = '51.4998'")
        page.evaluate("document.querySelector('input[name=\"longitude\"]').value = '-0.1247'")
        page.get_by_role("button", name="Add Customer").click()
        page.get_by_role("link", name="Back to Dashboard").click()
        page.get_by_role("link", name="Create New Job").click()
        page.get_by_label("Customer").select_option(label=customer_name)
        page.get_by_label("Date").fill(schedule_date.strftime("%Y-%m-%d"))

        # Verify smart availability: Only Worker A (who works Mondays) should be in the list
        expect(page.locator("#worker_id")).to_contain_text(worker_a_user)
        expect(page.locator("#worker_id")).not_to_contain_text(worker_b_user)
        print("Smart availability check passed.")

        page.get_by_label("Assign to Worker").select_option(label=worker_a_user)
        page.get_by_label("Location").fill("Final Test Location")
        page.get_by_label("Estimated Duration (minutes)").fill("120") # 2 hours
        page.get_by_role("button", name="Create Job").click()

        # Step 4: Verify Allocation Dashboard
        print("Verifying allocation dashboard...")
        page.get_by_role("link", name="Staff Allocation").click()
        expect(page.get_by_role("heading", name="Staff Allocation for the Week")).to_be_visible()

        # Check Worker A's row
        worker_a_row = page.locator("tr", has_text=worker_a_user)
        expect(worker_a_row.locator("td").nth(1)).to_have_text("2.00") # 2 hours assigned
        expect(worker_a_row.locator("td").nth(2)).to_have_text("40.00") # 40 hours contracted
        expect(worker_a_row).to_have_class(re.compile(r"table-warning")) # Should be under-allocated

        # Check Worker B's row
        worker_b_row = page.locator("tr", has_text=worker_b_user)
        expect(worker_b_row.locator("td").nth(1)).to_have_text("0.00")
        expect(worker_b_row.locator("td").nth(2)).to_have_text("30.00")
        expect(worker_b_row).to_have_class(re.compile(r"table-secondary")) # Should be unassigned

        print("Allocation dashboard verified.")

        screenshot_path = "jules-scratch/verification/allocation_dashboard.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot taken: {screenshot_path}")

    finally:
        browser.close()

with sync_playwright() as p:
    run_verification(p)
