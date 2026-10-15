import { Fragment, type ReactNode } from "react";

/**
 * A catalog sentence with slots (a link inside the sentence): the catalog returns the whole sentence as parts,
 * with the slots in their place, so no component glues a sentence from fragments.
 */
export function Rich({ parts }: { readonly parts: readonly ReactNode[] }) {
  return (
    <>
      {parts.map((part, index) => (
        // The parts of one sentence never reorder: the index is a stable key.
        <Fragment key={index}>{part}</Fragment>
      ))}
    </>
  );
}
