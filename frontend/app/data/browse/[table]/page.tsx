import TableDetail from "../../../../components/TableDetail";

export function generateMetadata({ params }: { params: { table: string } }) {
  return { title: params.table };
}

export default function BrowseTablePage({ params }: { params: { table: string } }) {
  return <TableDetail table={params.table} />;
}
