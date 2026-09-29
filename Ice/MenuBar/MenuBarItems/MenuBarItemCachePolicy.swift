//
//  MenuBarItemCachePolicy.swift
//  Ice
//

/// Decides whether the existing cache can safely skip another discovery pass.
enum MenuBarItemCachePolicy {
    static func shouldRefresh(
        cachedWindowIDs: [UInt32],
        currentWindowIDs: [UInt32],
        hasManagedItems: Bool
    ) -> Bool {
        // Window IDs can stay fixed while an AX lookup temporarily fails.
        // An empty cache is not evidence of a successful discovery pass.
        !hasManagedItems || cachedWindowIDs != currentWindowIDs
    }
}
