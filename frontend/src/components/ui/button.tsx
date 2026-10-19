import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[8px] text-[0.8rem] font-semibold transition-[background,border-color,color,box-shadow] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'border border-[#1d4ed8] bg-[#2563eb] text-white shadow-[0_1px_2px_rgba(15,27,45,0.12)] hover:bg-[#1d4ed8]',
        brand:
          'border border-transparent bg-[linear-gradient(135deg,#7347ff,#1769ff)] text-white shadow-[0_8px_18px_-10px_rgba(74,78,255,0.6)] hover:shadow-[0_10px_22px_-10px_rgba(74,78,255,0.7)] hover:brightness-[1.04]',
        soft: 'border border-[#cfe0fd] bg-[#e3edfe] text-[#1d4ed8] hover:border-[#b7cffb] hover:bg-[#d4e3fd]',
        outline:
          'border border-[var(--border-strong)] bg-white text-[var(--text)] shadow-[0_1px_2px_rgba(15,27,45,0.05)] hover:border-[#c2cbd8] hover:bg-[var(--surface-2)]',
        ghost: 'text-[var(--text-dim)] hover:bg-[var(--surface-3)] hover:text-[var(--text)]',
        danger:
          'border border-[#f8caca] bg-[#fef2f2] text-[#b91c1c] hover:border-[#f4b0b0] hover:bg-[#fde4e4]',
        success:
          'border border-[#15803d] bg-[#16a34a] text-white shadow-[0_1px_2px_rgba(15,27,45,0.12)] hover:bg-[#15803d]',
      },
      size: {
        default: 'h-8 px-3.5',
        icon: 'size-8',
        sm: 'h-7 px-2.5 text-xs',
        lg: 'h-10 px-5 text-sm',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  return <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
