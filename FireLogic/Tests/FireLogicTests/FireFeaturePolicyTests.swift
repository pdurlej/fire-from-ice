//
//  FireFeaturePolicyTests.swift
//  FireLogicTests
//

import XCTest
@testable import FireLogic

final class FireFeaturePolicyTests: XCTestCase {
    func testFreshInstallDefaultsToMenuBarOnly() {
        XCTAssertEqual(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: nil,
                storedMCPServerEnabled: nil,
                storedMCPAllowWrites: nil,
                legacyAIQuotasEnabled: false,
                hasStoredTriggers: false
            ),
            .init(
                experimentalFeaturesEnabled: false,
                mcpServerEnabled: false,
                mcpAllowWrites: false
            )
        )
    }

    func testExplicitStoredChoiceWinsOverLegacySignals() {
        XCTAssertEqual(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: false,
                storedMCPServerEnabled: true,
                storedMCPAllowWrites: true,
                legacyAIQuotasEnabled: true,
                hasStoredTriggers: true
            ),
            .init(
                experimentalFeaturesEnabled: false,
                mcpServerEnabled: true,
                mcpAllowWrites: true
            )
        )
    }

    func testLegacyAdvancedUseIsPreserved() {
        let state = FireFeaturePolicy.initialOptionalFeatureState(
            storedExperimentalFeaturesEnabled: nil,
            storedMCPServerEnabled: nil,
            storedMCPAllowWrites: nil,
            legacyAIQuotasEnabled: false,
            hasStoredTriggers: true
        )
        XCTAssertTrue(state.experimentalFeaturesEnabled)
        XCTAssertFalse(state.mcpServerEnabled)
        XCTAssertFalse(state.mcpAllowWrites)
    }

    func testLegacyAIQuotasKeepsRuntimeWithoutEnablingMCP() {
        let state = FireFeaturePolicy.initialOptionalFeatureState(
            storedExperimentalFeaturesEnabled: nil,
            storedMCPServerEnabled: true,
            storedMCPAllowWrites: true,
            legacyAIQuotasEnabled: true,
            hasStoredTriggers: false
        )
        XCTAssertTrue(state.experimentalFeaturesEnabled)
        XCTAssertFalse(state.mcpServerEnabled)
        XCTAssertFalse(state.mcpAllowWrites)
    }

    func testAutomaticallySeededLegacyMCPDoesNotEnableAnyOptionalFeature() {
        XCTAssertEqual(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: nil,
                storedMCPServerEnabled: true,
                storedMCPAllowWrites: true,
                legacyAIQuotasEnabled: false,
                hasStoredTriggers: false
            ),
            .init(
                experimentalFeaturesEnabled: false,
                mcpServerEnabled: false,
                mcpAllowWrites: false
            )
        )
    }

    func testDeliberateReadOnlyMCPEnablesExperimentalFeatures() {
        // fire.10.4 never seeds server-on/writes-off, so that pair is the
        // user's own choice and survives the upgrade.
        XCTAssertEqual(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: nil,
                storedMCPServerEnabled: true,
                storedMCPAllowWrites: false,
                legacyAIQuotasEnabled: false,
                hasStoredTriggers: false
            ),
            .init(
                experimentalFeaturesEnabled: true,
                mcpServerEnabled: true,
                mcpAllowWrites: false
            )
        )
    }

    func testMCPServerOffDoesNotEnableExperimentalFeatures() {
        XCTAssertEqual(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: nil,
                storedMCPServerEnabled: false,
                storedMCPAllowWrites: true,
                legacyAIQuotasEnabled: false,
                hasStoredTriggers: false
            ),
            .init(
                experimentalFeaturesEnabled: false,
                mcpServerEnabled: false,
                mcpAllowWrites: false
            )
        )
    }

    func testStoredOffKeepsNestedConfigurationForLaterOptIn() {
        // Turning Experimental off must not wipe what the user configured.
        XCTAssertEqual(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: false,
                storedMCPServerEnabled: true,
                storedMCPAllowWrites: false,
                legacyAIQuotasEnabled: false,
                hasStoredTriggers: false
            ),
            .init(
                experimentalFeaturesEnabled: false,
                mcpServerEnabled: true,
                mcpAllowWrites: false
            )
        )
    }

    func testStoredOnIsPreservedWithoutLegacySignals() {
        XCTAssertTrue(
            FireFeaturePolicy.initialOptionalFeatureState(
                storedExperimentalFeaturesEnabled: true,
                storedMCPServerEnabled: nil,
                storedMCPAllowWrites: nil,
                legacyAIQuotasEnabled: false,
                hasStoredTriggers: false
            ).experimentalFeaturesEnabled
        )
    }

    func testExperimentalPanesFollowTheSwitch() {
        XCTAssertFalse(FireFeaturePolicy.isExperimentalPaneVisible(experimentalFeaturesEnabled: false))
        XCTAssertTrue(FireFeaturePolicy.isExperimentalPaneVisible(experimentalFeaturesEnabled: true))
    }
}

final class TriggerRuntimePolicyTests: XCTestCase {
    func testPausedRuntimeDoesNotEvaluateTriggers() {
        XCTAssertFalse(TriggerRuntimePolicy.shouldEvaluate(isRunning: false))
    }

    func testRunningRuntimeEvaluatesTriggers() {
        XCTAssertTrue(TriggerRuntimePolicy.shouldEvaluate(isRunning: true))
    }
}
