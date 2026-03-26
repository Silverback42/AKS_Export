import { Badge } from "@/components/ui/badge"

const COLORS: Record<string, string> = {
  HIGH: "bg-green-100 text-green-800 border-green-300",
  MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-300",
  LOW: "bg-red-100 text-red-800 border-red-300",
  CORRECTED: "bg-blue-100 text-blue-800 border-blue-300",
}

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <Badge variant="outline" className={COLORS[confidence] ?? "bg-gray-100 text-gray-800 border-gray-300"}>
      {confidence}
    </Badge>
  )
}
