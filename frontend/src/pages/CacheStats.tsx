import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CacheStat {
  tool_slug: string;
  cache_status: string;
  cacheable: boolean;
}

export default function CacheStats() {
  const [stats, setStats] = useState<CacheStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet("/api/cache/stats").then((res) => {
      setStats(res.stats || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <p className="text-muted-foreground">Loading real cache stats...</p>;

  const hits = stats.filter((s) => s.cache_status === "hit").length;
  const misses = stats.filter((s) => s.cache_status === "miss").length;
  const bypass = stats.filter((s) => s.cache_status === "bypass").length;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Cache Statistics</h1>
        <p className="text-muted-foreground mt-1">
          Real cache events from Aperture's cache interceptor
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Cache Hits</p>
            <p className="text-2xl font-semibold text-emerald-600">{hits}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Cache Misses</p>
            <p className="text-2xl font-semibold text-amber-600">{misses}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Bypassed</p>
            <p className="text-2xl font-semibold text-blue-600">{bypass}</p>
            <p className="text-xs text-muted-foreground">writes/auth not cached</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Cache Events</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground text-left">
                <th className="pb-2 font-medium">Tool</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Cacheable</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {stats.map((stat, i) => (
                <tr key={i}>
                  <td className="py-2 font-mono text-xs">{stat.tool_slug}</td>
                  <td className="py-2">
                    <Badge
                      variant={
                        stat.cache_status === "hit"
                          ? "default"
                          : stat.cache_status === "miss"
                          ? "secondary"
                          : "outline"
                      }
                    >
                      {stat.cache_status}
                    </Badge>
                  </td>
                  <td className="py-2">
                    <Badge variant={stat.cacheable ? "secondary" : "destructive"}>
                      {stat.cacheable ? "Yes" : "No"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
