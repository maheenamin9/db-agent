import RelationshipsPanel from "../../components/RelationshipsPanel";

export default function RelationshipsPage() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-1">Relationships</h1>
      <p className="text-sm text-gray-600 mb-6">
        Define how tables join. This is the same list shown on the Semantics page.
      </p>
      <RelationshipsPanel />
    </div>
  );
}
