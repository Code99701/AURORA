import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

test.describe("AURORA End-to-End User Journey", () => {
  test("complete flow: register -> create workspace -> upload document -> research desk", async ({
    page,
  }) => {
    const timestamp = Date.now();
    const testUser = {
      displayName: "Playwright E2E Tester",
      email: `e2e_user_${timestamp}@example.com`,
      password: "Password123!Secure",
    };
    const workspaceTitle = `E2E Workspace ${timestamp}`;

    // 1. Visit registration page
    await page.goto("/register");
    await expect(page).toHaveTitle(/AURORA/);

    // 2. Fill registration form
    await page.fill('input[type="text"]', testUser.displayName);
    await page.fill('input[type="email"]', testUser.email);
    await page.fill('input[type="password"]', testUser.password);
    await page.click('button[type="submit"]');

    // 3. Verify redirected to /workspaces
    await page.waitForURL("**/workspaces", { timeout: 20000 });
    await expect(page.locator("h1")).toContainText("Research Workspaces");

    // 4. Create a new workspace
    await page.click('button:has-text("Create New Workspace")');
    await page.fill("#workspace-title-input", workspaceTitle);
    await page.fill("#workspace-desc-input", "E2E testing of the full RAG pipeline and document parsing.");
    await page.click('button[type="submit"]:has-text("Create Workspace")');

    // 5. Verify navigation to the new workspace page
    await page.waitForURL(/\/workspaces\/[0-9a-f-]+/, { timeout: 20000 });
    await expect(page.locator(`text=${workspaceTitle}`)).toBeVisible();

    // 6. Switch to Document Pipeline tab to upload sample file
    await page.locator("#documents-tab").click();
    await expect(page.locator("#source-upload")).toBeAttached({ timeout: 10000 });

    // Create a temporary sample TXT file
    const sampleFileName = `sample-${timestamp}.txt`;
    const sampleFilePath = path.join(process.cwd(), sampleFileName);
    fs.writeFileSync(
      sampleFilePath,
      "AURORA is a high-performance Multilingual Retrieval-Augmented Generation platform. " +
        "It features pgvector 768-dimensional embeddings, Tesseract OCR for English and Hindi, " +
        "and strict grounded citations."
    );

    try {
      // Set the file into the file input #source-upload
      const fileInput = page.locator("#source-upload");
      await fileInput.setInputFiles(sampleFilePath);

      // Wait for the document to appear in the documents list
      await expect(page.locator(`text=${sampleFileName}`)).toBeVisible({ timeout: 25000 });

      // Wait for the automatic processing and indexing pipeline to finish
      await expect(page.getByText("1 ready across this workspace")).toBeVisible({ timeout: 30000 });

      // 7. Switch back to Research Desk tab
      await page.locator("#research-tab").click();
      await expect(page.locator("#research-panel")).toBeVisible({ timeout: 10000 });

      // 8. Create a new conversation using the visible button
      const newConvBtn = page.locator('button:has-text("New conversation"):visible').first();
      await newConvBtn.click();

      // 9. Verify query input is active and enabled
      const queryInput = page.locator("#conversation-query");
      await expect(queryInput).toBeEnabled({ timeout: 15000 });

      // 10. Submit inquiry
      await queryInput.fill("What are the key capabilities and specifications of AURORA?");
      const askButton = page.locator('button:has-text("Ask AURORA")');
      if (await askButton.isVisible()) {
        await askButton.click();
      } else {
        await queryInput.press("Enter");
      }

      // 11. Wait for message bubble to appear with user question
      await expect(page.getByText("capabilities and specifications")).toBeVisible({ timeout: 30000 });
    } finally {
      if (fs.existsSync(sampleFilePath)) {
        fs.unlinkSync(sampleFilePath);
      }
    }
  });
});
