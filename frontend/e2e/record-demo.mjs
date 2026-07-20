import { copyFile, mkdir, rm } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium, expect } from '@playwright/test'

const frontendDirectory = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = resolve(frontendDirectory, '..')
const recordingDirectory = join(repositoryDirectory, 'docs', 'demo')
const temporaryVideoDirectory = join(recordingDirectory, '.playwright-video')
const outputPath = join(recordingDirectory, 'chatroom-e2e.webm')
const baseUrl = process.env.CHATROOM_E2E_URL ?? 'http://127.0.0.1:5173'
const studentGradesPath = join(repositoryDirectory, 'mock_services', 'data', 'student_grades.csv')

await mkdir(temporaryVideoDirectory, { recursive: true })

const browser = await chromium.launch()
const context = await browser.newContext({
  colorScheme: 'light',
  recordVideo: {
    dir: temporaryVideoDirectory,
    size: { width: 1440, height: 900 },
  },
  viewport: { width: 1440, height: 900 },
})
const page = await context.newPage()
const video = page.video()

async function pause(milliseconds = 800) {
  await page.waitForTimeout(milliseconds)
}

async function moveTo(locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  if (!box) {
    throw new Error('Could not determine the target location for the demo cursor.')
  }

  await page.evaluate(
    ({ x, y }) => {
      const cursor = document.querySelector('[data-e2e-cursor]')
      if (cursor instanceof HTMLElement) {
        cursor.style.transform = `translate(${x}px, ${y}px)`
      }
    },
    { x: box.x + box.width / 2, y: box.y + box.height / 2 },
  )
  await pause(350)
}

async function demoClick(locator) {
  await moveTo(locator)
  await locator.click({ delay: 120 })
  await pause()
}

async function demoType(locator, text) {
  await moveTo(locator)
  await locator.click()
  await locator.pressSequentially(text, { delay: 18 })
  await pause(500)
}

async function setChapter(text) {
  await page.evaluate((chapter) => {
    const badge = document.querySelector('[data-e2e-badge]')
    if (badge instanceof HTMLElement) {
      badge.textContent = chapter
    }
  }, text)
  await pause(900)
}

async function askQuestion(question, expectedAnswer) {
  const composer = page.getByPlaceholder('Message ChatRoom…')
  await demoType(composer, question)
  await demoClick(page.getByRole('button', { name: 'Send message' }))
  await expect(composer).toBeEnabled({ timeout: 120_000 })

  const answer = page.locator('.gpt-message[data-role="assistant"] .gpt-message-body').last()
  await expect(answer).toBeVisible()
  await expect(answer).toContainText(expectedAnswer)
  await pause(1200)
  return answer
}

let recordingError
try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'How can I help you today?' })).toBeVisible()

  await page.addStyleTag({
    content: `
      [data-e2e-cursor] {
        background: rgba(16, 163, 127, 0.18);
        border: 2px solid #10a37f;
        border-radius: 999px;
        height: 24px;
        left: -12px;
        pointer-events: none;
        position: fixed;
        top: -12px;
        transition: transform 320ms ease;
        width: 24px;
        z-index: 10000;
      }
      [data-e2e-badge] {
        background: rgba(13, 13, 13, 0.82);
        border-radius: 999px;
        bottom: 16px;
        color: white;
        font: 600 11px/1 system-ui, sans-serif;
        letter-spacing: 0.04em;
        padding: 8px 11px;
        pointer-events: none;
        position: fixed;
        right: 16px;
        text-transform: uppercase;
        z-index: 9999;
      }
    `,
  })
  await page.evaluate(() => {
    const cursor = document.createElement('div')
    cursor.dataset.e2eCursor = ''
    cursor.style.transform = 'translate(720px, 450px)'
    document.body.append(cursor)

    const badge = document.createElement('div')
    badge.dataset.e2eBadge = ''
    badge.textContent = 'Portfolio E2E · local'
    document.body.append(badge)
  })
  await pause(1500)

  await setChapter('1 · Review predefined connector tools')
  await demoClick(page.getByRole('button', { name: 'Inspect', exact: true }))
  const inspect = page.getByRole('complementary', { name: 'Inspect' })
  await expect(inspect).toBeVisible()
  await demoClick(inspect.getByRole('tab', { name: /Tools/ }))
  await expect(inspect.getByRole('tab', { name: /Tools \(2\)/ })).toBeVisible()
  await expect(inspect.locator('details.tool-card')).toHaveCount(2)
  await expect(inspect.getByText('Sales pipeline — Snowflake query', { exact: true })).toBeVisible()
  await expect(
    inspect.getByText('Account lookup — External API service', { exact: true }),
  ).toBeVisible()
  await expect(
    inspect.getByText('Pre-configured tool — Backend configuration', { exact: true }),
  ).toHaveCount(2)

  const snowflakeTool = inspect.locator('details').filter({ hasText: 'query_snowflake' })
  await demoClick(snowflakeTool.locator('summary'))
  await expect(snowflakeTool.getByText('Parameters')).toBeVisible()
  await pause(900)
  await demoClick(snowflakeTool.locator('summary'))

  const accountTool = inspect.locator('details').filter({ hasText: 'lookup_account' })
  await demoClick(accountTool.locator('summary'))
  await expect(accountTool.getByText('Parameters')).toBeVisible()
  await pause(900)
  await demoClick(accountTool.locator('summary'))
  await demoClick(inspect.getByRole('button', { name: 'Close', exact: true }))

  await setChapter('2 · Import a CSV knowledge base')
  await demoClick(page.getByRole('button', { name: 'Knowledge', exact: true }))
  const dialog = page.getByRole('dialog', { name: 'Settings' })
  await expect(dialog).toBeVisible()
  await demoType(dialog.getByPlaceholder('Name, e.g. Q4 Pipeline'), 'Student Grades')
  const fileInput = dialog.locator('input[type="file"]')
  await moveTo(fileInput)
  await fileInput.setInputFiles(studentGradesPath)
  await pause(900)
  await demoClick(dialog.getByRole('button', { name: 'Upload CSV', exact: true }))
  await expect(dialog.getByText('Student Grades', { exact: true })).toBeVisible()
  await pause(1000)

  await setChapter('3 · Configure specialist agents')
  await demoClick(dialog.getByRole('button', { name: /Back/ }))
  await demoClick(dialog.locator('button').filter({ hasText: 'Create agent' }))

  await demoType(dialog.getByPlaceholder('Agent name'), 'Student Success Analyst')
  await demoType(
    dialog.getByPlaceholder('What should this agent do?'),
    'Use the Student Grades knowledge base to answer student performance questions with concise, evidence-backed findings.',
  )
  await demoClick(dialog.locator('button').filter({ hasText: 'Student Grades' }))
  await demoClick(dialog.getByRole('button', { name: 'Create', exact: true }))
  await expect(dialog.getByText('Student Success Analyst', { exact: true })).toBeVisible()
  await pause(700)

  await demoClick(dialog.locator('button').filter({ hasText: 'Create agent' }))

  await demoType(dialog.getByPlaceholder('Agent name'), 'Revenue Analyst')
  await demoType(
    dialog.getByPlaceholder('What should this agent do?'),
    'Analyze Closed Won deals only using the Sales pipeline. Keep findings concise and create visual summaries when requested.',
  )
  await demoClick(dialog.locator('button').filter({ hasText: 'Sales pipeline' }))
  await demoClick(dialog.getByRole('button', { name: 'Create', exact: true }))
  await expect(dialog.getByText('Revenue Analyst', { exact: true })).toBeVisible()
  await pause(1000)
  await demoClick(dialog.getByRole('button', { name: 'Close', exact: true }))

  await setChapter('4 · Analyze Closed Won revenue')
  const salesQuestion =
    'For Closed Won deals only, summarize revenue by region and create a bar chart.'
  await askQuestion(salesQuestion, /\$349,500|East/)

  await setChapter('5 · Inspect orchestration and artifacts')
  await demoClick(page.getByRole('button', { name: 'Inspect', exact: true }))
  await expect(inspect).toBeVisible()
  await expect(inspect.getByRole('tab', { name: /Artifacts \(1\)/ })).toBeVisible()

  await demoClick(inspect.getByRole('tab', { name: /Trace/ }))
  await expect(inspect.getByText('manager started', { exact: true })).toBeVisible()
  const salesToolResult = inspect.locator('.event-row[data-event-type="tool_finished"]').first()
  await moveTo(salesToolResult)
  await pause(1600)

  await demoClick(inspect.getByRole('tab', { name: /Artifacts/ }))
  await expect(inspect.getByText('Revenue by Region (bar)')).toBeVisible()
  await pause(2000)

  await demoClick(inspect.getByRole('button', { name: 'Close', exact: true }))
  await demoClick(page.getByRole('button', { name: 'New chat', exact: true }))

  await setChapter('6 · Use a configured API connector')
  const accountQuestion = 'Look up account AC-1001 and summarize its current status.'
  await askQuestion(accountQuestion, /Northwind Traders|active/)
  await demoClick(page.getByRole('button', { name: 'Inspect', exact: true }))
  await expect(inspect.getByRole('tab', { name: /Trace/ })).toBeVisible()
  const accountToolResult = inspect.locator('.event-row[data-event-type="tool_finished"]').first()
  await moveTo(accountToolResult)
  await pause(1500)

  await demoClick(inspect.getByRole('button', { name: 'Close', exact: true }))
  await demoClick(page.getByRole('button', { name: 'New chat', exact: true }))

  await setChapter('7 · Let the supervisor route a student question')
  const studentQuestion = 'Which students have the highest GPA? Summarize the result.'
  const studentAnswer = await askQuestion(studentQuestion, /Olivia Rahman|9\.3/)
  await demoClick(page.getByRole('button', { name: 'Inspect', exact: true }))
  await expect(inspect.getByRole('tab', { name: /Trace/ })).toBeVisible()
  const knowledgeToolResult = inspect.locator('.event-row[data-event-type="tool_finished"]').first()
  await moveTo(knowledgeToolResult)
  await pause(1700)

  await setChapter('8 · Review the expanded tool catalog')
  await demoClick(inspect.getByRole('tab', { name: /Tools/ }))
  await expect(inspect.getByRole('tab', { name: /Tools \(3\)/ })).toBeVisible()
  await expect(inspect.locator('details.tool-card')).toHaveCount(3)
  await expect(inspect.getByText('Student Grades', { exact: true })).toBeVisible()
  await expect(
    inspect.getByText('Dynamically generated tool — CSV upload', { exact: true }),
  ).toBeVisible()
  await pause(1200)

  const knowledgeTool = inspect.locator('details').filter({ hasText: 'query_dataset_' })
  await demoClick(knowledgeTool.locator('summary'))
  await expect(knowledgeTool.getByText('Parameters')).toBeVisible()
  await pause(1700)

  await demoClick(inspect.getByRole('button', { name: 'Close', exact: true }))
  await setChapter('9 · Verify persistent conversation history')
  await demoClick(page.getByRole('button', { name: 'New chat', exact: true }))
  await expect(page.getByRole('heading', { name: 'How can I help you today?' })).toBeVisible()
  await expect(page.getByRole('button', { name: /^For Closed Won deals only/ })).toBeVisible()
  await expect(page.getByRole('button', { name: accountQuestion, exact: true })).toBeVisible()
  const studentHistory = page.getByRole('button', {
    name: studentQuestion,
    exact: true,
  })
  await expect(studentHistory).toBeVisible()
  await pause(1200)
  await demoClick(studentHistory)
  await expect(studentAnswer).toBeVisible()

  await setChapter('10 · Review configurable LLM providers')
  const providerSelector = page.getByRole('button', { name: 'LLM provider: Ollama' })
  await expect(providerSelector).toBeVisible()
  await demoClick(providerSelector)
  const providerMenu = page.getByRole('listbox', { name: 'Available LLM providers' })
  await expect(providerMenu).toBeVisible()
  await expect(providerMenu.getByRole('option', { name: 'Ollama: Active · Configured' })).toBeVisible()
  await expect(providerMenu.getByRole('option', { name: 'OpenAI: Not configured' })).toBeVisible()
  await expect(providerMenu.getByRole('option', { name: 'Bedrock: Not configured' })).toBeVisible()
  await expect(
    providerMenu.getByText(
      'Additional providers become selectable when configured in the backend.',
    ),
  ).toBeVisible()
  await pause(1800)

  await setChapter('E2E complete · Multi-agent tools + configurable LLMs')
  await pause(1800)
} catch (error) {
  recordingError = error
} finally {
  await context.close()
  await browser.close()
}

if (!video) {
  throw new Error('Playwright did not create a video for the page.')
}

const recordedPath = await video.path()
if (recordingError) {
  await rm(temporaryVideoDirectory, { recursive: true, force: true })
  throw recordingError
}

await copyFile(recordedPath, outputPath)
await rm(temporaryVideoDirectory, { recursive: true, force: true })

console.log(`Recorded E2E demo: ${outputPath}`)
