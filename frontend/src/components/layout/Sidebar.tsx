import { Link, useLocation } from "react-router-dom"
import { FolderOpen, LayoutDashboard } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Projekte", href: "/projects", icon: FolderOpen },
]

export function Sidebar() {
  const location = useLocation()

  return (
    <aside className="flex w-60 flex-col border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <LayoutDashboard className="mr-2 h-5 w-5 text-primary" />
        <span className="text-lg font-semibold">AKS Export</span>
      </div>
      <nav className="flex-1 p-3">
        {navItems.map((item) => {
          const active = location.pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
