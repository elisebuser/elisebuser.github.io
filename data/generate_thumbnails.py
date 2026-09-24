from PIL import Image, ImageOps
import json
import os
import re
import shutil
import sys


# ==========================
# Base folder
# ==========================

base_folder = "/Users/ebuser/Documents/EB_Website_Folder"

# Public Cloudflare R2 base URL for the uploaded EB_Website_Folder.
# Keep the trailing slash because the website appends collection/image paths.
image_base_url = (
    "https://pub-81f0405a7471418c8f41a932f79f6163.r2.dev/"
    "EB_Website_Folder/"
)


# ==========================
# Settings
# ==========================

thumbnail_size = (400, 400)
title_thumbnail_size = (399, 399)

thumbnail_quality = 85
title_thumbnail_quality = 90

half_resolution_quality = 95
half_resolution_subsampling = 0

image_extensions = (
    ".jpg",
    ".jpeg",
    ".png"
)

title_folder_name = "title_thumbnail"
title_output_filename = "collection_thumbnail.jpg"

thumbnails_folder_name = "thumbnails"
half_resolution_folder_name = "originals_half_resolution"

orientation_exif_tag = 274
gps_exif_tag = 34853


def natural_sort_key(filename):
    """Sort text alphabetically while treating digit groups as numbers."""

    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", filename)
    ]


def list_images(folder):
    """Return supported image files in deterministic natural-sort order."""

    return sorted(
        [
            filename
            for filename in os.listdir(folder)
            if filename.lower().endswith(image_extensions)
        ],
        key=natural_sort_key
    )


def clear_generated_folder(folder):
    """Delete generated files while preserving the folder itself."""

    os.makedirs(
        folder,
        exist_ok=True
    )

    for entry in os.listdir(folder):
        path = os.path.join(
            folder,
            entry
        )

        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)


def read_photo_credits(collection_path):
    """Read photo credits from photo_credits.txt.

    Each non-empty credit line should have the form:
        filename.jpg | Credit Name
    """
    credits_path = os.path.join(
        collection_path,
        "photo_credits.txt"
    )

    if not os.path.exists(
        credits_path
    ):
        return {}

    credits = {}

    with open(
        credits_path,
        "r",
        encoding="utf-8"
    ) as file:
        for line_number, line in enumerate(
            file,
            start=1
        ):
            line = line.strip()

            if not line:
                continue

            if "|" not in line:
                print(
                    "  WARNING: Ignoring malformed credit line "
                    f"{line_number} in photo_credits.txt"
                )
                continue

            filename, credit = line.split(
                "|",
                1
            )

            filename = filename.strip()
            credit = credit.strip()

            if not filename or not credit:
                print(
                    "  WARNING: Ignoring incomplete credit line "
                    f"{line_number} in photo_credits.txt"
                )
                continue

            credits[filename] = credit

    return credits


def update_photo_credits(
    collection_path,
    original_image_files,
    current_image_files,
    credits
):
    """Update photo_credits.txt so credits follow renamed images.

    The mapping is based on each original filename's position in the
    complete, naturally sorted image list before and after normalization.
    This also handles adding a new image that causes existing numbered
    images to shift.
    """
    if not credits:
        return {}

    credits_path = os.path.join(
        collection_path,
        "photo_credits.txt"
    )

    # The script assigns the new sequential filename based on the image's
    # position in the current sorted list. Build that mapping before any
    # renaming has taken place.
    filename_mapping = {}

    current_by_old_name = {
        filename: filename
        for filename in current_image_files
    }

    for old_filename in original_image_files:
        if old_filename not in current_by_old_name:
            continue

        index = current_image_files.index(
            old_filename
        )

        extension = os.path.splitext(
            old_filename
        )[1].lower()

        new_filename = (
            f"{(index + 1) * 100}" +
            extension
        )

        filename_mapping[old_filename] = new_filename

    updated_credits = {}
    unresolved_credits = []

    for filename, credit in credits.items():
        if filename in filename_mapping:
            updated_filename = filename_mapping[filename]
            updated_credits[updated_filename] = credit
        elif filename in current_image_files:
            updated_credits[filename] = credit
        else:
            unresolved_credits.append(
                (filename, credit)
            )

    if unresolved_credits:
        for filename, _credit in unresolved_credits:
            print(
                "  WARNING: Could not match credit to an image: "
                f"{filename}"
            )

    with open(
        credits_path,
        "w",
        encoding="utf-8"
    ) as file:
        for filename, credit in updated_credits.items():
            file.write(
                f"{filename} | {credit}\n"
            )

    print(
        "  Updated photo_credits.txt"
    )

    return updated_credits


def original_names_need_normalizing(image_files):
    """Check whether originals need sequential 100, 200, 300... names."""

    return any(
        filename !=
        f"{(index + 1) * 100}" +
        f"{os.path.splitext(filename)[1].lower()}"
        for index, filename in enumerate(image_files)
    )


def normalize_original_names(
    originals_folder,
    image_files
):
    """
    Rename originals without recompressing or changing their image data.

    Temporary names prevent collisions when files exchange positions.

    Returns:
        (renamed, filename_mapping)
    """
    if not original_names_need_normalizing(
        image_files
    ):
        print(
            "  Original filenames already normalized"
        )

        identity_mapping = {
            filename: filename
            for filename in image_files
        }

        return False, identity_mapping

    # The final names are determined by the complete sorted list.
    filename_mapping = {}

    for index, filename in enumerate(
        image_files,
        start=1
    ):
        extension = os.path.splitext(
            filename
        )[1].lower()

        filename_mapping[filename] = (
            f"{index * 100}" +
            extension
        )

    temporary_files = []

    for index, filename in enumerate(
        image_files
    ):
        old_path = os.path.join(
            originals_folder,
            filename
        )

        extension = os.path.splitext(
            filename
        )[1].lower()

        temporary_name = (
            f"__tmp_{index:06d}" +
            extension
        )

        temporary_path = os.path.join(
            originals_folder,
            temporary_name
        )

        os.rename(
            old_path,
            temporary_path
        )

        temporary_files.append(
            temporary_name
        )

    for index, filename in enumerate(
        temporary_files,
        start=1
    ):
        extension = os.path.splitext(
            filename
        )[1].lower()

        old_path = os.path.join(
            originals_folder,
            filename
        )

        new_name = (
            f"{index * 100}" +
            extension
        )

        new_path = os.path.join(
            originals_folder,
            new_name
        )

        os.rename(
            old_path,
            new_path
        )

    print(
        f"  Renamed {len(temporary_files)} images"
    )

    return True, filename_mapping


def cleaned_exif_bytes(image):
    """
    Preserve useful EXIF metadata while removing orientation and GPS.

    Orientation is removed because ImageOps.exif_transpose permanently
    applies it to the derivative pixels. GPS is intentionally excluded
    from web derivatives.
    """

    exif = image.getexif()

    if orientation_exif_tag in exif:
        del exif[orientation_exif_tag]

    if gps_exif_tag in exif:
        del exif[gps_exif_tag]

    if len(exif) == 0:
        return None

    return exif.tobytes()


def jpeg_save_options(source_image):
    """Build metadata-preserving JPEG save options."""

    options = {
        "format": "JPEG",
        "quality": half_resolution_quality,
        "subsampling": half_resolution_subsampling,
        "optimize": True,
        "progressive": True
    }

    exif_bytes = cleaned_exif_bytes(
        source_image
    )

    if exif_bytes:
        options["exif"] = exif_bytes

    icc_profile = source_image.info.get(
        "icc_profile"
    )

    if icc_profile:
        options["icc_profile"] = icc_profile

    dpi = source_image.info.get(
        "dpi"
    )

    if (
        isinstance(dpi, tuple) and
        len(dpi) == 2
    ):
        options["dpi"] = dpi

    return options


def half_resolution_filename(original_filename):
    """Half-resolution derivatives are always high-quality JPEG files."""

    stem = os.path.splitext(
        original_filename
    )[0]

    return f"{stem}.jpg"


def half_resolution_needs_update(
    original_path,
    half_resolution_path
):
    """
    Regenerate when missing or when the source has a newer timestamp.
    """

    if not os.path.exists(
        half_resolution_path
    ):
        return True

    return (
        os.stat(
            original_path
        ).st_mtime_ns >
        os.stat(
            half_resolution_path
        ).st_mtime_ns
    )


def create_half_resolution_image(
    original_path,
    output_path
):
    """
    Create a JPEG with half the source width and half the source height.

    Example: 6000 x 4000 becomes 3000 x 2000.
    """

    temporary_output = (
        output_path +
        ".tmp"
    )

    try:
        with Image.open(
            original_path
        ) as source_image:
            save_options = jpeg_save_options(
                source_image
            )

            oriented_image = ImageOps.exif_transpose(
                source_image
            )

            width, height = oriented_image.size

            target_size = (
                max(
                    1,
                    width // 2
                ),
                max(
                    1,
                    height // 2
                )
            )

            resized_image = oriented_image.resize(
                target_size,
                Image.Resampling.LANCZOS
            )

            if resized_image.mode != "RGB":
                resized_image = resized_image.convert(
                    "RGB"
                )

            resized_image.save(
                temporary_output,
                **save_options
            )

        os.replace(
            temporary_output,
            output_path
        )

    finally:
        if os.path.exists(
            temporary_output
        ):
            os.remove(
                temporary_output
            )


def create_or_update_title_thumbnail(
    collection_path
):
    """Create the square collection title thumbnail when supplied."""

    title_folder = os.path.join(
        collection_path,
        title_folder_name
    )

    if not os.path.exists(
        title_folder
    ):
        print(
            "  No title_thumbnail folder found"
        )

        return

    title_images = [
        filename
        for filename in os.listdir(
            title_folder
        )
        if (
            filename.lower().endswith(
                image_extensions
            ) and
            filename !=
                title_output_filename
        )
    ]

    if not title_images:
        return

    input_file = os.path.join(
        title_folder,
        title_images[0]
    )

    output_file = os.path.join(
        title_folder,
        title_output_filename
    )

    try:
        with Image.open(
            input_file
        ) as source_image:
            image = ImageOps.exif_transpose(
                source_image
            )

            width, height = image.size

            if width != height:
                print(
                    "  ERROR: Title image is not square "
                    f"({width}x{height})"
                )

                return

            image = image.resize(
                title_thumbnail_size,
                Image.Resampling.LANCZOS
            )

            if image.mode not in (
                "RGB",
                "L"
            ):
                image = image.convert(
                    "RGB"
                )

            image.save(
                output_file,
                quality=title_thumbnail_quality,
                optimize=True
            )

        os.remove(
            input_file
        )

        print(
            "  Created collection_thumbnail.jpg"
        )

    except Exception as error:
        print(
            "  Error processing title thumbnail: "
            f"{error}"
        )


def process_collection(
    collection,
    collection_path
):
    """Process one photo collection and return its JSON entry."""

    print(
        f"\nProcessing collection: {collection}"
    )

    originals_folder = os.path.join(
        collection_path,
        "originals"
    )

    if not os.path.exists(
        originals_folder
    ):
        print(
            "  No originals folder found"
        )

        return None

    original_images_before_rename = list_images(
        originals_folder
    )

    photo_credits = read_photo_credits(
        collection_path
    )

    originals_names_changed, _filename_mapping = (
        normalize_original_names(
            originals_folder,
            original_images_before_rename
        )
    )

    original_images = list_images(
        originals_folder
    )

    if photo_credits:
        # Build the final-name mapping from the position of each old
        # filename in the complete current sorted image list. This is what
        # allows credits to follow an existing image when a newly added
        # image causes the numbered filenames to shift.
        current_position_mapping = {}

        for old_filename in original_images_before_rename:
            if old_filename not in original_images:
                continue

            index = original_images.index(
                old_filename
            )

            extension = os.path.splitext(
                old_filename
            )[1].lower()

            current_position_mapping[
                old_filename
            ] = (
                f"{(index + 1) * 100}" +
                extension
            )

        updated_photo_credits = {}

        for old_filename, credit in photo_credits.items():
            if old_filename in current_position_mapping:
                updated_photo_credits[
                    current_position_mapping[old_filename]
                ] = credit
            elif old_filename in original_images:
                updated_photo_credits[
                    old_filename
                ] = credit
            else:
                print(
                    "  WARNING: Could not match credit to an image: "
                    f"{old_filename}"
                )

        credits_path = os.path.join(
            collection_path,
            "photo_credits.txt"
        )

        with open(
            credits_path,
            "w",
            encoding="utf-8"
        ) as file:
            for filename, credit in updated_photo_credits.items():
                file.write(
                    f"{filename} | {credit}\n"
                )

        photo_credits = updated_photo_credits

        print(
            "  Updated photo_credits.txt"
        )

    thumbnails_folder = os.path.join(
        collection_path,
        thumbnails_folder_name
    )

    half_resolution_folder = os.path.join(
        collection_path,
        half_resolution_folder_name
    )

    os.makedirs(
        thumbnails_folder,
        exist_ok=True
    )

    os.makedirs(
        half_resolution_folder,
        exist_ok=True
    )

    if originals_names_changed:
        print(
            "  Original filenames changed; "
            "clearing thumbnails folder"
        )

        clear_generated_folder(
            thumbnails_folder
        )

        print(
            "  Original filenames changed; "
            "clearing half-resolution folder"
        )

        clear_generated_folder(
            half_resolution_folder
        )

    create_or_update_title_thumbnail(
        collection_path
    )

    image_count = 0
    aspect_ratios = []

    expected_half_resolution_files = set()

    for filename in original_images:
        image_count += 1

        original_path = os.path.join(
            originals_folder,
            filename
        )

        thumbnail_path = os.path.join(
            thumbnails_folder,
            filename
        )

        half_filename = half_resolution_filename(
            filename
        )

        expected_half_resolution_files.add(
            half_filename.casefold()
        )

        half_resolution_path = os.path.join(
            half_resolution_folder,
            half_filename
        )

        try:
            with Image.open(
                original_path
            ) as source_image:
                image = ImageOps.exif_transpose(
                    source_image
                )

                width, height = image.size

                aspect_ratios.append(
                    round(
                        width /
                        max(
                            1,
                            height
                        ),
                        6
                    )
                )

                if os.path.exists(
                    thumbnail_path
                ):
                    print(
                        f"  Thumbnail exists: {filename}"
                    )
                else:
                    thumbnail_image = image.copy()

                    thumbnail_image.thumbnail(
                        thumbnail_size,
                        Image.Resampling.LANCZOS
                    )

                    if thumbnail_image.mode not in (
                        "RGB",
                        "L"
                    ):
                        thumbnail_image = (
                            thumbnail_image.convert(
                                "RGB"
                            )
                        )

                    thumbnail_image.save(
                        thumbnail_path,
                        quality=thumbnail_quality,
                        optimize=True
                    )

                    print(
                        f"  Created thumbnail: {filename}"
                    )

            if half_resolution_needs_update(
                original_path,
                half_resolution_path
            ):
                create_half_resolution_image(
                    original_path,
                    half_resolution_path
                )

                print(
                    "  Created half-resolution image: "
                    f"{half_filename}"
                )
            else:
                print(
                    "  Half-resolution image current: "
                    f"{half_filename}"
                )

        except Exception as error:
            aspect_ratios.append(
                1.0
            )

            print(
                f"  Error processing {filename}: "
                f"{error}"
            )

    for filename in os.listdir(
        half_resolution_folder
    ):
        path = os.path.join(
            half_resolution_folder,
            filename
        )

        if (
            os.path.isfile(path) and
            filename.casefold() not in
                expected_half_resolution_files
        ):
            os.remove(
                path
            )

            print(
                "  Removed stale half-resolution image: "
                f"{filename}"
            )

    if collection.lower() == "blank":
        print(
            "  Skipped blank collection "
            "in collections.json"
        )

        return None

    collection_entry = {
        "name": collection,
        "images": image_count,
        "aspect_ratios": aspect_ratios
    }

    if photo_credits:
        collection_entry["credits"] = photo_credits

    return collection_entry


def main():
    """Process every collection and write collections.json."""

    processing_base_folder = (
        os.path.abspath(
            os.path.expanduser(
                sys.argv[1]
            )
        )
        if len(sys.argv) > 1
        else base_folder
    )

    if not os.path.isdir(processing_base_folder):
        raise FileNotFoundError(
            "Local image folder not found: "
            f"{processing_base_folder}"
        )

    collections = []

    for collection in sorted(
        os.listdir(
            processing_base_folder
        ),
        key=natural_sort_key
    ):
        collection_path = os.path.join(
            processing_base_folder,
            collection
        )

        if not os.path.isdir(
            collection_path
        ):
            continue

        collection_entry = process_collection(
            collection,
            collection_path
        )

        if collection_entry is not None:
            collections.append(
                collection_entry
            )

    json_path = os.path.join(
        processing_base_folder,
        "collections.json"
    )

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            {
                "base": image_base_url,
                "collections": collections
            },
            file,
            indent=4
        )

    print(
        "\nGenerated:"
    )

    print(
        json_path
    )

    print(
        "\nAll processing complete."
    )


if __name__ == "__main__":
    main()
