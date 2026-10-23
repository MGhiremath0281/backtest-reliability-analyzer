import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface FindingsBreakdownChartProps {
  data: Array<{
    name: string;
    count: number;
    color?: string;
  }>;
  title?: string;
}

export const FindingsBreakdownChart: React.FC<FindingsBreakdownChartProps> = ({
  data,
  title,
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center font-mono text-xs text-zinc-500 border border-dashed border-zinc-300">
        No findings data to visualize.
      </div>
    );
  }

  const defaultColors = ['#ff3b30', '#d97706', '#4a8b9f', '#09090b', '#71717a'];

  return (
    <div className="w-full">
      {title && (
        <div className="text-xs font-mono font-bold uppercase tracking-wider text-black mb-3">
          {title}
        </div>
      )}
      <div className="h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="2 2" stroke="#e4e4e7" vertical={false} />
            <XAxis
              dataKey="name"
              stroke="#09090b"
              fontSize={11}
              fontFamily="monospace"
              tickLine={false}
            />
            <YAxis
              stroke="#09090b"
              fontSize={11}
              fontFamily="monospace"
              allowDecimals={false}
              tickLine={false}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-white border border-black p-2 font-mono text-xs shadow-[2px_2px_0px_0px_#000000]">
                      <div className="font-bold">{payload[0].payload.name}</div>
                      <div className="text-zinc-600">Count: {payload[0].value}</div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="count" stroke="#000000" strokeWidth={1}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color || defaultColors[index % defaultColors.length]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
