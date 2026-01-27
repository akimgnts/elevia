import * as React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { cn } from "../../lib/cn";

export const ToastProvider = ToastPrimitive.Provider;
export const ToastViewport = React.forwardRef<
  HTMLOListElement,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Viewport
    ref={ref}
    className={cn(
      "fixed top-4 right-4 z-50 flex max-h-screen w-[340px] flex-col gap-2 outline-none",
      className
    )}
    {...props}
  />
));

ToastViewport.displayName = "ToastViewport";

export const Toast = React.forwardRef<
  HTMLLIElement,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Root>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Root
    ref={ref}
    className={cn(
      "card-boost flex w-full items-start gap-3 rounded-2xl px-4 py-3 shadow-soft",
      className
    )}
    {...props}
  />
));

Toast.displayName = "Toast";

export const ToastTitle = React.forwardRef<
  HTMLHeadingElement,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Title>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Title
    ref={ref}
    className={cn("text-sm font-semibold text-slate-900", className)}
    {...props}
  />
));

ToastTitle.displayName = "ToastTitle";

export const ToastDescription = React.forwardRef<
  HTMLParagraphElement,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Description>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Description
    ref={ref}
    className={cn("text-sm text-slate-600", className)}
    {...props}
  />
));

ToastDescription.displayName = "ToastDescription";

export const ToastClose = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Close>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Close
    ref={ref}
    className={cn(
      "ml-auto text-xs font-semibold text-slate-500 hover:text-slate-900",
      className
    )}
    {...props}
  />
));

ToastClose.displayName = "ToastClose";
