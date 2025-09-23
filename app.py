#!/usr/bin/env python
import os
import argparse
from pathlib import Path
import warnings
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import ConnectionPatch, Circle

# --- CONFIGURATION ---
CURRENT_FOLDER = Path(__file__).parent.resolve()
PIPELINE_OUTPUT_DIRECTORY = Path(f"{CURRENT_FOLDER}_1")
MAX_EPOCHS_PER_MOSAIC = 15
TARGET_CLASSIFICATIONS = ['Gold', 'Silver', 'Bronze']
APERTURE_RADIUS_PIXELS = 6 # Radius of the yellow circle to draw on images

# Map classifications to colors for highlighting in plot titles
CLASSIFICATION_COLORS = {
    'Gold': 'gold',
    'Silver': 'silver',
    'Bronze': '#CD7F32'
}

# --- CORE FUNCTIONS ---

def get_visual_paths(base_folder: Path, row: pd.Series) -> dict:
    """
    Constructs paths for the essential science and difference visual PNGs.
    """
    paths = {'sci': None, 'diff': None}
    try:
        object_name = row['object_name']
        filter_name = row['filter']
        frame_id = int(row['frame_id'])
        
        visual_base = base_folder / object_name / "visuals" / filter_name
        
        sci_path = visual_base / "science_frames" / f"frame_{frame_id}.png"
        diff_path = visual_base / "difference_frames" / f"frame_{frame_id}.png"
        
        if sci_path.exists(): paths['sci'] = sci_path
        if diff_path.exists(): paths['diff'] = diff_path
            
    except (KeyError, ValueError, TypeError):
        pass
        
    return paths


def generate_variability_mosaic(dataframe: pd.DataFrame, object_folder: Path, title: str, output_path: Path):
    """
    Creates a 2-panel chronological mosaic with simple, straight arrows
    connecting the date labels and a circle showing the measurement aperture.
    """
    if dataframe.empty:
        tqdm.write(f"      - No detections to generate mosaic for '{title}'. Skipping.")
        return

    n_epochs = len(dataframe)
    ncols = 2
    
    fig, axes = plt.subplots(n_epochs, ncols, figsize=(10, 4 * n_epochs), facecolor='darkgray')
    
    if n_epochs == 1:
        axes = axes.reshape(1, -1)

    for i, (idx, row) in enumerate(dataframe.iterrows()):
        ax_sci, ax_diff = axes[i, 0], axes[i, 1]
        
        image_paths = get_visual_paths(object_folder.parent, row)

        for ax, img_type in zip([ax_sci, ax_diff], ['sci', 'diff']):
            path = image_paths[img_type]
            if path:
                try:
                    img = mpimg.imread(path)
                    ax.imshow(img)
                    center_y, center_x = img.shape[0] / 2, img.shape[1] / 2

                    aperture_circle = Circle(
                        (center_x, center_y),
                        radius=APERTURE_RADIUS_PIXELS,
                        facecolor='none',
                        edgecolor='yellow',
                        linewidth=1.5,
                        linestyle='--'
                    )
                    ax.add_patch(aperture_circle)

                    ax.plot(center_x, center_y, '+', color='red', markersize=12, markeredgewidth=1.5)

                except Exception as e:
                    ax.text(0.5, 0.5, "Error\nLoading", ha='center', va='center', color='red')
            else:
                ax.set_facecolor('black')
                ax.text(0.5, 0.5, "Image\nNot Found", ha='center', va='center', color='white')
            
            ax.set_xticks([])
            ax.set_yticks([])

        if i == 0:
            ax_sci.set_title("Science", color='white', fontweight='bold')
            ax_diff.set_title("Difference", color='white', fontweight='bold')
        
        classification = row['classification']
        mag = row['forcediffim_mag']
        jd = row['jd']
        label_color = CLASSIFICATION_COLORS.get(classification, 'white')
        row_label_text = f"JD: {jd:.2f}\nMag: {mag:.2f}\n({classification})"
        
        y_pos = axes[i, 0].get_position().y0 + axes[i, 0].get_position().height / 2
        fig.text(0.15, y_pos, row_label_text, color=label_color, fontsize=12, 
                 fontweight='bold', ha='center', va='center')

        if i > 0:
            delta_jd = jd - dataframe.iloc[i-1]['jd']
            y_prev = axes[i-1, 0].get_position().y0 + axes[i-1, 0].get_position().height / 2
            
            xyA = (0.05, y_prev)
            xyB = (0.05, y_pos)

            # --- MODIFIED: Use a simple, straight arrow ---
            arrow = ConnectionPatch(
                xyA=xyA, xyB=xyB, coordsA="figure fraction", coordsB="figure fraction",
                arrowstyle="->,head_length=10,head_width=6", # A normal arrow
                color="red", linewidth=2
            )
            fig.add_artist(arrow)

            mid_y = (y_pos + y_prev) / 2
            fig.text(0.06, mid_y, f"+{delta_jd:.1f} d", ha='left', va='center', 
                     color='white', fontsize=10, 
                     bbox=dict(facecolor='black', alpha=0.7, boxstyle='round,pad=0.2'))

    plt.subplots_adjust(left=0.3, right=0.98, top=0.95, bottom=0.02, hspace=0.4)
    fig.suptitle(title, fontsize=20, color='white')
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='darkgray')
    plt.close(fig)


def create_mosaics_for_object(obj_folder: Path):
    object_name = obj_folder.name
    tqdm.write(f"\n--- Processing Mosaics for {object_name} ---")
    
    report_path = obj_folder / "analysis" / f"{object_name}_frame_report.csv"
    if not report_path.exists():
        tqdm.write(f"No frame report found for {object_name}. Skipping.")
        return

    try:
        df_report = pd.read_csv(report_path)
        df_report['forcediffim_mag'] = pd.to_numeric(df_report['forcediffim_mag'], errors='coerce')
        df_report.dropna(subset=['forcediffim_mag', 'jd'], inplace=True)
    except (pd.errors.EmptyDataError, KeyError):
        tqdm.write(f"Frame report for {object_name} is empty or invalid. Skipping.")
        return
        
    for band_filter, group_df in df_report.groupby('filter'):
        band_code = str(band_filter).split('_')[-1]
        tqdm.write(f"  - Analyzing filter: {band_code}")

        df_high_confidence = group_df[group_df['classification'].isin(TARGET_CLASSIFICATIONS)].copy()

        if df_high_confidence.empty:
            tqdm.write(f"    - No high-confidence detections for filter {band_code}. Skipping.")
            continue

        df_chronological = df_high_confidence.sort_values(by='jd').head(MAX_EPOCHS_PER_MOSAIC)
        
        tqdm.write(f"    - Found {len(df_chronological)} epochs to create variability mosaic.")

        mosaic_folder = obj_folder / "analysis" / "mosaics"
        output_path = mosaic_folder / f"{object_name}_{band_code}_variability_mosaic.png"
        title = f"Variability Check: {object_name} ({band_code}-band)"

        generate_variability_mosaic(
            dataframe=df_chronological,
            object_folder=obj_folder,
            title=title,
            output_path=output_path
        )
        tqdm.write(f"    - Variability mosaic saved in: {mosaic_folder}")


def main():
    parser = argparse.ArgumentParser(description="Assemble chronological mosaics for visual variability verification.")
    parser.add_argument("--input_dir", default=PIPELINE_OUTPUT_DIRECTORY, type=Path, help=f"Path to the main pipeline output directory (default: {PIPELINE_OUTPUT_DIRECTORY})")
    args = parser.parse_args()
    input_dir = args.input_dir
    
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"ERROR: Input directory not found at '{input_dir}'")
        return
    
    print(f"\n--- Generating Chronological Variability Mosaics ---")
    print(f"Scanning for reports in: {input_dir}")

    object_folders = sorted([d for d in input_dir.iterdir() if d.is_dir() and d.name.startswith('SMDG')])
    if not object_folders:
        print("No valid object folders (starting with 'SMDG') found."); return
    print(f"Found {len(object_folders)} objects to process.")

    for obj_folder in tqdm(object_folders, desc="Processing Objects", unit="object"):
        create_mosaics_for_object(obj_folder)

    print("\n--- All Mosaics Generated! ---")

if __name__ == "__main__":
    warnings.filterwarnings('ignore', category=UserWarning)
    import matplotlib
    matplotlib.use("Agg")
    main()