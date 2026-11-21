import { X } from "lucide-react";
import type { Group } from "@/types/run";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { AREA_MANAGERS } from "@/lib/areaManagers";
import { ALL, EMPTY_FILTERS, isFiltered, type FilterState } from "@/lib/filters";
import { moveLabel } from "@/lib/format";

function Pick({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label} className="h-9 w-full bg-card text-sm sm:w-auto sm:min-w-[150px]">
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All {label.toLowerCase()}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function Filters({
  value,
  onChange,
  groups,
  cities,
  shown,
}: {
  value: FilterState;
  onChange: (f: FilterState) => void;
  groups: Group[];
  cities: string[];
  shown: number;
}) {
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });
  const categories = Array.from(new Set(groups.map((g) => g.category).filter(Boolean))).sort();
  const types = (["WH_TO_STORE", "STORE_TO_STORE", "PULL_BACK"] as const).filter((t) => groups.some((g) => g.type === t));

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
        <Pick label="Types" value={value.type} onChange={(type) => set({ type })} options={types.map((t) => ({ value: t, label: moveLabel(t) }))} />
        <Pick label="Cities" value={value.city} onChange={(city) => set({ city })} options={cities.map((c) => ({ value: c, label: c }))} />
        <Pick
          label="Area managers"
          value={value.am}
          onChange={(am) => set({ am })}
          options={AREA_MANAGERS.map((a) => ({ value: a.id, label: `${a.name} · ${a.city}` }))}
        />
        <Pick label="Categories" value={value.category} onChange={(category) => set({ category })} options={categories.map((c) => ({ value: c, label: c }))} />
        <label className="col-span-2 flex items-center gap-2 text-sm sm:col-span-1 sm:ml-1">
          <Checkbox checked={value.signoffOnly} onCheckedChange={(c) => set({ signoffOnly: c === true })} />
          Needs sign-off only
        </label>
      </div>
      {isFiltered(value) && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          {value.store !== ALL && (
            <span className="inline-flex items-center gap-1 rounded-full border bg-card px-2.5 py-0.5 text-xs font-medium text-foreground">
              Store {value.store}
              <button type="button" aria-label="Clear store filter" onClick={() => set({ store: ALL })} className="rounded hover:text-maroon">
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
          <span className="tnum">{shown} moves match</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-sm" onClick={() => onChange(EMPTY_FILTERS)}>
            Clear filters
          </Button>
        </div>
      )}
    </div>
  );
}
