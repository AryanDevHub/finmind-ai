import { Briefcase, Car, Clapperboard, GraduationCap, HeartPulse, Package, ShoppingBag, TrendingUp, Utensils, Zap, type LucideIcon } from "lucide-react";
import type { Category } from "@/types";

/** Icon + glow colour per category. */
export const CATEGORY_META: Record<Category, { icon: LucideIcon; color: string }> = {
  Food: { icon: Utensils, color: "#FB923C" },
  Transport: { icon: Car, color: "#38BDF8" },
  Shopping: { icon: ShoppingBag, color: "#F472B6" },
  Entertainment: { icon: Clapperboard, color: "#A78BFA" },
  Bills: { icon: Zap, color: "#FBBF24" },
  Health: { icon: HeartPulse, color: "#34D399" },
  Education: { icon: GraduationCap, color: "#60A5FA" },
  Salary: { icon: Briefcase, color: "#2DD4BF" },
  Investment: { icon: TrendingUp, color: "#4ADE80" },
  Other: { icon: Package, color: "#94A3B8" },
};
