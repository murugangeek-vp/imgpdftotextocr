import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Toaster } from 'react-hot-toast'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'OCR Platform — Extract Text from Images & PDFs',
  description:
    'Enterprise-grade OCR platform supporting all 22 Indian scheduled languages plus global scripts. ' +
    'Extract text from scanned documents, invoices, prescriptions, and more with AI-powered accuracy.',
  keywords: 'OCR, text extraction, Indian languages, PDF, image, Hindi, Tamil, Telugu, document AI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#1e1e2e',
              color: '#cdd6f4',
              border: '1px solid #313244',
            },
          }}
        />
      </body>
    </html>
  )
}
