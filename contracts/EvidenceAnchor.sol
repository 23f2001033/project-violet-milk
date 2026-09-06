// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title EvidenceAnchor
 * @notice Records that a document digest existed at or before a given block.
 *
 * WHAT AN ANCHOR PROVES
 *   The digest existed no later than the block it was anchored in, and the
 *   record cannot be altered afterwards by the party that made it.
 *
 * WHAT IT DOES NOT PROVE  — read this before repeating any claim about it
 *   - It does NOT prove who authored the document. Anyone may anchor any
 *     digest, including one they did not produce.
 *   - It does NOT make the document tamper-proof. It makes a later
 *     SUBSTITUTION detectable: a modified PDF hashes differently and will not
 *     match the anchored value.
 *   - `block.timestamp` is set by the block proposer and can drift by seconds.
 *     Treat the anchor as "at or before this block", never as a precise clock.
 *
 * The anchoring account is recorded so a dossier can state WHO anchored a
 * digest, not merely that someone did.
 */
contract EvidenceAnchor {
    struct Anchor {
        uint64  blockTime;    // block.timestamp when anchored
        uint64  blockNumber;  // block height, the stronger ordering signal
        address anchoredBy;   // the account that submitted it
    }

    mapping(bytes32 => Anchor) private _anchors;

    event EvidenceAnchored(
        bytes32 indexed digest,
        address indexed anchoredBy,
        uint64  blockTime,
        uint64  blockNumber
    );

    error AlreadyAnchored(bytes32 digest, uint64 blockNumber);
    error EmptyDigest();

    /**
     * @notice Anchor a SHA-256 digest. First write wins.
     * @dev Re-anchoring reverts rather than overwriting: the earliest record
     *      is the evidentially meaningful one, and silently replacing it would
     *      let a later party claim an earlier document's timestamp.
     */
    function anchor(bytes32 digest) external {
        if (digest == bytes32(0)) revert EmptyDigest();

        Anchor storage existing = _anchors[digest];
        if (existing.blockNumber != 0) {
            revert AlreadyAnchored(digest, existing.blockNumber);
        }

        _anchors[digest] = Anchor({
            blockTime: uint64(block.timestamp),
            blockNumber: uint64(block.number),
            anchoredBy: msg.sender
        });

        emit EvidenceAnchored(
            digest, msg.sender, uint64(block.timestamp), uint64(block.number)
        );
    }

    /// @notice Full anchor record. blockNumber == 0 means never anchored.
    function anchorOf(bytes32 digest)
        external
        view
        returns (uint64 blockTime, uint64 blockNumber, address anchoredBy)
    {
        Anchor storage a = _anchors[digest];
        return (a.blockTime, a.blockNumber, a.anchoredBy);
    }

    /// @notice Convenience check for a verifier.
    function isAnchored(bytes32 digest) external view returns (bool) {
        return _anchors[digest].blockNumber != 0;
    }
}
