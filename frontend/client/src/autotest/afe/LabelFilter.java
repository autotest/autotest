package autotest.afe;

import autotest.common.table.MultipleListFilter;

public class LabelFilter extends MultipleListFilter {
    public static final int VISIBLE_SIZE = 10;
    
    public LabelFilter() {
        super("multiple_labels", VISIBLE_SIZE);
        setMatchAllText("All labels");
        setChoices(AfeUtils.getLabelStrings());
    }

    protected String getItemText(int index) {
        return AfeUtils.decodeLabelName(super.getItemText(index));
    }
}
