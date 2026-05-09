import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ResultSkeletonProps {
  cards?: number;
  showDetail?: boolean;
}

export default function ResultSkeleton({ cards = 3, showDetail = true }: ResultSkeletonProps) {
  return (
    <div className="space-y-4">
      <div className={`grid gap-4 grid-cols-${Math.min(cards, 4)}`}>
        {Array.from({ length: cards }).map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-6 space-y-3">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-3 w-40" />
            </CardContent>
          </Card>
        ))}
      </div>
      {showDetail && (
        <Card>
          <CardContent className="pt-6 space-y-3">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
            <div className="flex flex-wrap gap-1 pt-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-5 w-20" />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
