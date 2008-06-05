package afeclient.client;

import afeclient.client.table.MultipleListFilter;

public class LabelFilter extends MultipleListFilter {
    public static final int VISIBLE_SIZE = 10;
    
    public LabelFilter() {
        super("multiple_labels", VISIBLE_SIZE);
        setMatchAllText("All labels");
        setChoices(Utils.getLabelStrings());
    }

    protected String getItemText(int index) {
        return Utils.decodeLabelName(super.getItemText(index));
    }
}
